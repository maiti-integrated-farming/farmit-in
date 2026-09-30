"""
Data Archival System for FarmIt
Automatically archives data older than 1 year from Neon DB to Supabase
"""
import gzip
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


class DataArchivalManager:
    """Manages the archival of old data from Neon DB to Supabase."""
    
    def __init__(self, neon_uri: str, supabase_uri: str, archival_age_years: int = 1):
        """
        Initialize the archival manager.
        
        Args:
            neon_uri: Connection string for Neon DB (primary database)
            supabase_uri: Connection string for Supabase (archive database)
            archival_age_years: Archive data older than this many years (default: 1)
        """
        self.neon_uri = neon_uri
        self.supabase_uri = supabase_uri
        self.archival_age_years = archival_age_years
        self.cutoff_date = datetime.utcnow() - timedelta(days=365 * archival_age_years)
        
        # Create engines
        self.neon_engine = create_engine(neon_uri)
        self.supabase_engine = create_engine(supabase_uri)
        
        logger.info(f"Initialized archival manager with cutoff date: {self.cutoff_date}")
    
    def get_archivable_tables(self) -> List[Dict[str, Any]]:
        """
        Get list of tables that contain time-series data to be archived.
        
        Returns:
            List of dictionaries with table info (name, date_column, organization_column)
        """
        return [
            # Animal-related tables
            {'name': 'animals', 'date_column': 'created_at', 'org_column': 'farm_id', 'join_farm': True},
            {'name': 'animal_movements', 'date_column': 'movement_date', 'org_column': 'farm_id'},
            {'name': 'animal_weights', 'date_column': 'weight_date', 'org_column': 'farm_id'},
            
            # Health records
            {'name': 'vaccinations', 'date_column': 'date', 'org_column': 'farm_id'},
            {'name': 'dewormings', 'date_column': 'date', 'org_column': 'farm_id'},
            {'name': 'treatments', 'date_column': 'date', 'org_column': 'farm_id'},
            
            # Breeding records
            {'name': 'breeding_records', 'date_column': 'mating_date', 'org_column': 'farm_id'},
            {'name': 'kidding_records', 'date_column': 'kidding_date', 'org_column': 'farm_id'},
            
            # Feed and inventory
            {'name': 'feed_consumptions', 'date_column': 'date', 'org_column': 'farm_id'},
            {'name': 'purchases', 'date_column': 'purchase_date', 'org_column': 'farm_id'},
            
            # Commercial
            {'name': 'animal_sales', 'date_column': 'sale_date', 'org_column': 'farm_id'},
            {'name': 'expenses', 'date_column': 'expense_date', 'org_column': 'farm_id'},
            {'name': 'milk_records', 'date_column': 'milking_date', 'org_column': 'farm_id'},
            
            # Audit logs
            {'name': 'audit_logs', 'date_column': 'timestamp', 'org_column': 'farm_id'},
        ]
    
    def compress_data(self, data: List[Dict]) -> bytes:
        """
        Compress data using gzip.
        
        Args:
            data: List of dictionaries (rows) to compress
            
        Returns:
            Compressed bytes
        """
        json_data = json.dumps(data, default=str)
        return gzip.compress(json_data.encode('utf-8'))
    
    def decompress_data(self, compressed_data: bytes) -> List[Dict]:
        """
        Decompress data from gzip.
        
        Args:
            compressed_data: Compressed bytes
            
        Returns:
            List of dictionaries (rows)
        """
        json_data = gzip.decompress(compressed_data).decode('utf-8')
        return json.loads(json_data)
    
    def archive_table(self, table_info: Dict[str, Any]) -> Dict[str, int]:
        """
        Archive old data from a specific table.
        
        Args:
            table_info: Dictionary with table name and date column
            
        Returns:
            Dictionary with counts: {'archived': X, 'deleted': Y}
        """
        table_name = table_info['name']
        date_column = table_info['date_column']
        
        logger.info(f"Starting archival for table: {table_name}")
        
        try:
            # Create sessions
            NeonSession = sessionmaker(bind=self.neon_engine)
            neon_session = NeonSession()
            
            # Query old data from Neon
            query = text(f"""
                SELECT * FROM {table_name}
                WHERE {date_column} < :cutoff_date
                ORDER BY {date_column}
            """)
            
            result = neon_session.execute(query, {'cutoff_date': self.cutoff_date})
            old_records = [dict(row._mapping) for row in result]
            
            if not old_records:
                logger.info(f"No records to archive for {table_name}")
                return {'archived': 0, 'deleted': 0}
            
            logger.info(f"Found {len(old_records)} records to archive from {table_name}")
            
            # Group by organization and year for efficient storage
            archived_data = self._group_by_org_year(old_records, table_info)
            
            # Store in Supabase archive table
            archived_count = self._store_in_archive(table_name, archived_data)
            
            # Delete from Neon (after successful archival)
            if archived_count > 0:
                record_ids = [r['id'] for r in old_records if 'id' in r]
                if record_ids:
                    delete_query = text(f"""
                        DELETE FROM {table_name}
                        WHERE id = ANY(:ids)
                    """)
                    neon_session.execute(delete_query, {'ids': record_ids})
                    neon_session.commit()
                    logger.info(f"Deleted {len(record_ids)} records from {table_name}")
            
            neon_session.close()
            
            return {'archived': archived_count, 'deleted': len(old_records)}
            
        except Exception as e:
            logger.error(f"Error archiving {table_name}: {str(e)}")
            return {'archived': 0, 'deleted': 0, 'error': str(e)}
    
    def _group_by_org_year(self, records: List[Dict], table_info: Dict) -> List[Dict]:
        """
        Group records by organization and year for compressed storage.
        
        Args:
            records: List of record dictionaries
            table_info: Table information including org column
            
        Returns:
            List of grouped archive entries
        """
        grouped = {}
        
        for record in records:
            # Get organization from farm_id if needed
            if table_info.get('join_farm'):
                # In production, you'd join with farms table to get org_id
                # For now, use farm_id as a proxy
                org_key = f"farm_{record.get('farm_id', 0)}"
            else:
                org_key = f"farm_{record.get(table_info['org_column'], 0)}"
            
            # Extract year from date column
            date_col = table_info['date_column']
            if date_col in record and record[date_col]:
                if isinstance(record[date_col], str):
                    year = record[date_col][:4]
                else:
                    year = str(record[date_col].year)
            else:
                year = 'unknown'
            
            key = f"{org_key}_{year}"
            
            if key not in grouped:
                grouped[key] = []
            
            grouped[key].append(record)
        
        # Create archive entries
        archive_entries = []
        for key, records_group in grouped.items():
            parts = key.split('_')
            org_identifier = '_'.join(parts[:-1])
            year = parts[-1]
            
            compressed_data = self.compress_data(records_group)
            
            archive_entries.append({
                'organization_identifier': org_identifier,
                'year': year,
                'record_count': len(records_group),
                'compressed_data': compressed_data,
                'compression_type': 'gzip',
                'archived_at': datetime.utcnow()
            })
        
        return archive_entries
    
    def _store_in_archive(self, source_table: str, archive_entries: List[Dict]) -> int:
        """
        Store compressed data in Supabase archive table.
        
        Args:
            source_table: Name of the source table
            archive_entries: List of archive entry dictionaries
            
        Returns:
            Number of records archived
        """
        SupabaseSession = sessionmaker(bind=self.supabase_engine)
        supabase_session = SupabaseSession()
        
        try:
            # Ensure archive table exists
            self._ensure_archive_table(source_table)
            
            total_records = 0
            
            for entry in archive_entries:
                # Insert into archive table
                insert_query = text(f"""
                    INSERT INTO archived_{source_table} 
                    (organization_identifier, year, record_count, compressed_data, 
                     compression_type, archived_at)
                    VALUES 
                    (:org_id, :year, :count, :data, :compression, :archived_at)
                """)
                
                supabase_session.execute(insert_query, {
                    'org_id': entry['organization_identifier'],
                    'year': entry['year'],
                    'count': entry['record_count'],
                    'data': entry['compressed_data'],
                    'compression': entry['compression_type'],
                    'archived_at': entry['archived_at']
                })
                
                total_records += entry['record_count']
            
            supabase_session.commit()
            logger.info(f"Archived {total_records} records to Supabase")
            
            return total_records
            
        except Exception as e:
            supabase_session.rollback()
            logger.error(f"Error storing in archive: {str(e)}")
            raise
        finally:
            supabase_session.close()
    
    def _ensure_archive_table(self, source_table: str):
        """
        Ensure the archive table exists in Supabase.
        
        Args:
            source_table: Name of the source table
        """
        archive_table_name = f"archived_{source_table}"
        
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {archive_table_name} (
            id SERIAL PRIMARY KEY,
            organization_identifier VARCHAR(100),
            year VARCHAR(4),
            record_count INTEGER,
            compressed_data BYTEA,
            compression_type VARCHAR(20),
            archived_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(organization_identifier, year)
        )
        """
        
        with self.supabase_engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
    
    def run_full_archival(self) -> Dict[str, Any]:
        """
        Run archival process for all tables.
        
        Returns:
            Summary of archival results
        """
        logger.info("Starting full archival process")
        start_time = datetime.utcnow()
        
        results = {
            'start_time': start_time,
            'tables_processed': 0,
            'total_archived': 0,
            'total_deleted': 0,
            'errors': []
        }
        
        tables = self.get_archivable_tables()
        
        for table_info in tables:
            try:
                result = self.archive_table(table_info)
                results['tables_processed'] += 1
                results['total_archived'] += result.get('archived', 0)
                results['total_deleted'] += result.get('deleted', 0)
                
                if 'error' in result:
                    results['errors'].append({
                        'table': table_info['name'],
                        'error': result['error']
                    })
                    
            except Exception as e:
                logger.error(f"Failed to archive {table_info['name']}: {str(e)}")
                results['errors'].append({
                    'table': table_info['name'],
                    'error': str(e)
                })
        
        results['end_time'] = datetime.utcnow()
        results['duration_seconds'] = (results['end_time'] - start_time).total_seconds()
        
        logger.info(f"Archival complete. Archived {results['total_archived']} records "
                   f"in {results['duration_seconds']:.2f} seconds")
        
        return results
    
    def query_archived_data(self, table_name: str, organization_id: int, 
                           year: int) -> List[Dict]:
        """
        Query and decompress archived data from Supabase.
        
        Args:
            table_name: Name of the source table
            organization_id: Organization ID
            year: Year to query
            
        Returns:
            List of decompressed records
        """
        archive_table_name = f"archived_{table_name}"
        org_identifier = f"farm_{organization_id}"
        
        query = text(f"""
            SELECT compressed_data, compression_type 
            FROM {archive_table_name}
            WHERE organization_identifier = :org_id AND year = :year
        """)
        
        with self.supabase_engine.connect() as conn:
            result = conn.execute(query, {
                'org_id': org_identifier,
                'year': str(year)
            }).fetchone()
            
            if result:
                compressed_data = result[0]
                return self.decompress_data(compressed_data)
            
            return []
    
    def get_combined_data(self, table_name: str, organization_id: int, 
                         start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Get combined data from both Neon (active) and Supabase (archived).
        Used for analytics that span multiple years.
        
        Args:
            table_name: Name of the table
            organization_id: Organization ID
            start_date: Start date for query
            end_date: End date for query
            
        Returns:
            Combined list of records from both databases
        """
        results = []
        
        # Query active data from Neon
        if end_date >= self.cutoff_date:
            NeonSession = sessionmaker(bind=self.neon_engine)
            neon_session = NeonSession()
            
            query = text(f"""
                SELECT * FROM {table_name}
                WHERE farm_id IN (
                    SELECT id FROM farms WHERE organization_id = :org_id
                )
                AND created_at BETWEEN :start_date AND :end_date
                ORDER BY created_at
            """)
            
            neon_result = neon_session.execute(query, {
                'org_id': organization_id,
                'start_date': max(start_date, self.cutoff_date),
                'end_date': end_date
            })
            
            results.extend([dict(row._mapping) for row in neon_result])
            neon_session.close()
        
        # Query archived data from Supabase for years before cutoff
        if start_date < self.cutoff_date:
            start_year = start_date.year
            end_year = min(end_date.year, self.cutoff_date.year)
            
            for year in range(start_year, end_year + 1):
                archived = self.query_archived_data(table_name, organization_id, year)
                
                # Filter by date range
                for record in archived:
                    record_date = record.get('created_at') or record.get('date')
                    if record_date:
                        if isinstance(record_date, str):
                            record_date = datetime.fromisoformat(record_date)
                        
                        if start_date <= record_date <= end_date:
                            results.append(record)
        
        # Sort combined results by date
        results.sort(key=lambda x: x.get('created_at') or x.get('date', datetime.min))
        
        return results


def run_archival_job():
    """
    Entry point for running the archival job (can be called by Celery or cron).
    """
    from flask import current_app
    
    if not current_app.config.get('DATA_ARCHIVAL_ENABLED'):
        logger.info("Data archival is disabled in configuration")
        return {'status': 'skipped', 'reason': 'disabled'}
    
    neon_uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    supabase_uri = current_app.config.get('ARCHIVE_DATABASE_URI')
    
    if not supabase_uri:
        logger.warning("Archive database URI not configured")
        return {'status': 'skipped', 'reason': 'no_archive_db'}
    
    archival_age = current_app.config.get('ARCHIVAL_AGE_YEARS', 1)
    
    manager = DataArchivalManager(neon_uri, supabase_uri, archival_age)
    results = manager.run_full_archival()
    
    return results

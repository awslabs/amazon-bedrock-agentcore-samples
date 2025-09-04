import json
import boto3
import psycopg2
import os
import re
import time
import logging
from datetime import datetime
from botocore.exceptions import ClientError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryComplexityError(Exception):
    """Custom exception for query complexity violations"""
    pass

class QueryLimitError(Exception):
    """Custom exception for query limit violations"""
    pass

def analyze_query_complexity(query):
    """
    Analyze query complexity and potential resource impact
    
    Args:
        query (str): SQL query to analyze
    
    Returns:
        dict: Complexity metrics
        
    Raises:
        QueryComplexityError: If query is too complex
    """
    query_lower = query.lower()
    complexity_score = 0
    warnings = []
    
    # Check for joins
    join_count = sum(1 for join_type in ['join', 'inner join', 'left join', 'right join', 'full join'] 
                    if join_type in query_lower)
    complexity_score += join_count * 2
    if join_count > 3:
        warnings.append(f"Query contains {join_count} joins - consider simplifying")
    
    # Check for subqueries
    subquery_count = query_lower.count('(select')
    complexity_score += subquery_count * 3
    if subquery_count > 2:
        warnings.append(f"Query contains {subquery_count} subqueries - consider restructuring")
    
    # Check for aggregations
    agg_functions = ['count(', 'sum(', 'avg(', 'max(', 'min(']
    agg_count = sum(query_lower.count(func) for func in agg_functions)
    complexity_score += agg_count
    
    # Check for window functions
    if 'over(' in query_lower or 'partition by' in query_lower:
        complexity_score += 3
        warnings.append("Query uses window functions - monitor performance")
    
    # Check for complex WHERE conditions
    where_pos = query_lower.find('where')
    if where_pos != -1:
        where_clause = query_lower[where_pos:]
        and_count = where_clause.count(' and ')
        or_count = where_clause.count(' or ')
        complexity_score += (and_count + or_count)
        if (and_count + or_count) > 5:
            warnings.append(f"Complex WHERE clause with {and_count + or_count} conditions")
    
    return {
        'complexity_score': complexity_score,
        'warnings': warnings,
        'join_count': join_count,
        'subquery_count': subquery_count,
        'aggregation_count': agg_count
    }

def validate_and_execute_queries(secret_name, query, max_rows=20, 
                               max_statements=5, max_total_rows=1000, 
                               max_complexity=15):
    """
    Enhanced query validation and execution with additional controls
    """
    response = {
        'results': [],
        'performance_metrics': None,
        'warnings': [],
        'optimization_suggestions': []
    }
    
    start_time = time.time()
    conn = None
    total_rows = 0
    
    try:
        # Validate and split queries
        statements = validate_query(query)
        
        # Check number of statements
        if len(statements) > max_statements:
            raise QueryLimitError(
                f"Too many statements ({len(statements)}). Maximum allowed is {max_statements}"
            )
        
        # Connect to database
        conn = connect_to_db(secret_name)
        
        with conn.cursor() as cur:
            # Set session parameters
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET statement_timeout = '30s'")
            cur.execute("SET idle_in_transaction_session_timeout = '60s'")
            
            # Execute each statement
            for stmt_index, stmt in enumerate(statements, 1):
                # Analyze query complexity
                complexity_metrics = analyze_query_complexity(stmt)
                if complexity_metrics['complexity_score'] > max_complexity:
                    raise QueryComplexityError(
                        f"Statement {stmt_index} is too complex (score: {complexity_metrics['complexity_score']})"
                    )
                
                # Add complexity warnings to response
                response['warnings'].extend(
                    f"Statement {stmt_index}: {warning}"
                    for warning in complexity_metrics['warnings']
                )
                
                stmt_response = {
                    'columns': [],
                    'rows': [],
                    'truncated': False,
                    'message': '',
                    'row_count': 0,
                    'query': stmt,
                    'complexity_metrics': complexity_metrics
                }
                
                stmt_lower = stmt.lower().strip()
                
                # Only add LIMIT for SELECT queries
                if stmt_lower.startswith('select') and 'limit' not in stmt_lower:
                    remaining_rows = max_total_rows - total_rows
                    limit_rows = min(max_rows, remaining_rows)
                    stmt = f"{stmt} LIMIT {limit_rows + 1}"
                
                # Execute with explain plan first for SELECT queries
                if stmt_lower.startswith('select'):
                    #cur.execute(f"EXPLAIN (FORMAT JSON) {stmt}")
                    #explain_plan = cur.fetchone()[0]
                    
                    # Analyze plan for potential issues
                    optimization_suggestions = analyze_query_performance(secret_name, stmt)
                    if optimization_suggestions:
                        response['optimization_suggestions'].extend(
                            f"Statement {stmt_index}: {suggestion}"
                            for suggestion in optimization_suggestions
                        )
                
                # Execute actual query
                cur.execute(stmt)
                
                # Get column names
                stmt_response['columns'] = [desc[0] for desc in cur.description]
                
                # Fetch results
                rows = cur.fetchall()
                row_count = len(rows)
                
                # Check total row limit
                total_rows += row_count
                if total_rows > max_total_rows:
                    stmt_response['truncated'] = True
                    excess_rows = total_rows - max_total_rows
                    rows = rows[:-excess_rows]
                    stmt_response['message'] = (
                        f"Results truncated. Maximum total rows ({max_total_rows}) reached"
                    )
                    total_rows = max_total_rows
                
                # Check individual statement limit
                elif row_count > max_rows:
                    stmt_response['truncated'] = True
                    rows = rows[:max_rows]
                    stmt_response['message'] = (
                        f"Results truncated to {max_rows} rows"
                    )
                
                stmt_response['row_count'] = len(rows)
                stmt_response['rows'] = [
                    dict(zip(stmt_response['columns'], row))
                    for row in rows
                ]
                
                response['results'].append(stmt_response)
            
            # Add overall performance metrics
            total_time = time.time() - start_time
            response['performance_metrics'] = {
                'execution_time': total_time,
                'statements_executed': len(statements),
                'total_rows': total_rows,
                'timestamp': datetime.utcnow().isoformat(),
                'needs_analysis': total_time > 5,
                'performance_message': (
                    f"Executed {len(statements)} statements in {total_time:.2f} seconds"
                )
            }
            
            # Add performance recommendations if needed
            if total_time > 5:
                response['warnings'].append(
                    "Query execution time exceeded 5 seconds. Consider optimization."
                )
            
            return response
                
    except (QueryComplexityError, QueryLimitError) as e:
        error_msg = str(e)
        logger.warning(error_msg)
        raise ValueError(error_msg)
        
    except psycopg2.Error as pe:
        error_msg = f"Database error: {str(pe)}"
        logger.error(error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    finally:
        if conn:
            conn.close()

def get_secret(secret_name):
    """Get secret from AWS Secrets Manager """
    secret_name = secret_name
    region_name = os.environ['REGION']
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    
    try:
        secret_value = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(secret_value['SecretString'])
        return secret
    except ClientError as e:
        raise Exception(f"Failed to get secret: {str(e)}")

def get_env_secret(environment):
    ssm_client = boto3.client('ssm')
    """Retrieve the secret name for the specified environment"""
    if environment == 'prod':
        try:
            # Get the secret name from Parameter Store
            response = ssm_client.get_parameter(
                Name=f'/AuroraOps/{environment}'
            )
            print(response['Parameter']['Value'])
            return response['Parameter']['Value']
        except ssm_client.exceptions.ParameterNotFound:
            error_message = f"Parameter not found: /AuroraOps/{environment}"
            print(error_message)
            raise Exception(error_message)
    elif environment == 'dev':
        try:
            # Get the secret name from Parameter Store
            response = ssm_client.get_parameter(
                Name=f'/AuroraOps/{environment}'
            )
            return response['Parameter']['Value']
        except Exception as e:
            raise Exception(f"Failed to get dev secret name from Parameter Store: {str(e)}")
    else:
        print("environement does not exist")
        raise ValueError(f"Unknown environment: {environment}")

def connect_to_db(secret_name):
    """Establish database connection"""
    cur_secret = secret_name
    secret = get_secret(cur_secret)
    try:
        conn = psycopg2.connect(
            host=secret['host'],
            database=secret['dbname'],
            user=secret['username'],
            password=secret['password'],
            port=secret['port']
        )
        return conn
    except Exception as e:
        raise Exception(f"Failed to connect to the database: {str(e)}")

# Define the queries dictionary for different object types
queries = {
    'table': """
        WITH RECURSIVE columns AS (
            SELECT 
                t.schemaname,
                t.tablename,
                array_to_string(
                    array_agg(
                        '    ' || quote_ident(a.attname) || ' ' || 
                        pg_catalog.format_type(a.atttypid, a.atttypmod) ||
                        CASE WHEN a.attnotnull THEN ' NOT NULL' ELSE '' END ||
                        CASE WHEN ad.adbin IS NOT NULL 
                            THEN ' DEFAULT ' || pg_get_expr(ad.adbin, ad.adrelid) 
                            ELSE '' 
                        END
                        ORDER BY a.attnum
                    ),
                    E',\n'
                ) as column_definitions
            FROM pg_catalog.pg_tables t
            JOIN pg_catalog.pg_class c 
                ON c.relname = t.tablename 
                AND c.relnamespace = (
                    SELECT oid 
                    FROM pg_catalog.pg_namespace 
                    WHERE nspname = t.schemaname
                )
            JOIN pg_catalog.pg_attribute a 
                ON a.attrelid = c.oid 
                AND a.attnum > 0 
                AND NOT a.attisdropped
            LEFT JOIN pg_catalog.pg_attrdef ad 
                ON ad.adrelid = c.oid 
                AND ad.adnum = a.attnum
            WHERE t.schemaname NOT IN ('pg_catalog', 'information_schema')
            GROUP BY t.schemaname, t.tablename
        )
        SELECT 
            col.schemaname || '.' || col.tablename as object_name,
            'TABLE' as object_type,
            CASE 
                WHEN col.column_definitions IS NOT NULL THEN
                    format(
                        'CREATE TABLE %I.%I (\n%s\n);',
                        col.schemaname,
                        col.tablename,
                        col.column_definitions
                    )
                ELSE 'ERROR: No columns found for this table'
            END as definition,
            obj_description(
                (col.schemaname || '.' || col.tablename)::regclass, 
                'pg_class'
            ) as description
        FROM columns col
        WHERE col.tablename ILIKE %s AND col.schemaname = %s
    """,

    'view': """
        SELECT 
            schemaname || '.' || viewname as object_name,
            'VIEW' as object_type,
            format(
                'CREATE OR REPLACE VIEW %I.%I AS\n%s',
                schemaname,
                viewname,
                pg_get_viewdef(format('%I.%I', schemaname, viewname)::regclass, true)
            ) as definition,
            obj_description(
                (schemaname || '.' || viewname)::regclass, 
                'pg_class'
            ) as description
        FROM pg_catalog.pg_views
        WHERE viewname ILIKE %s 
        AND schemaname = %s
        AND schemaname NOT IN ('pg_catalog', 'information_schema')
    """,

    'function': """
        SELECT 
            n.nspname || '.' || p.proname as object_name,
            'FUNCTION' as object_type,
            pg_get_functiondef(p.oid) as definition,
            obj_description(p.oid, 'pg_proc') as description,
            p.prorettype::regtype as return_type,
            p.provolatile,
            p.proparallel
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        WHERE p.proname ILIKE %s
        AND n.nspname = %s
        AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        AND p.prokind = 'f'  -- 'f' for function
    """,

    'procedure': """
        SELECT 
            n.nspname || '.' || p.proname as object_name,
            'PROCEDURE' as object_type,
            pg_get_functiondef(p.oid) as definition,
            obj_description(p.oid, 'pg_proc') as description
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        WHERE p.proname ILIKE %s
        AND n.nspname = %s
        AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        AND p.prokind = 'p'  -- 'p' for procedure
    """,

    'trigger': """
        SELECT 
            n.nspname || '.' || t.tgname as object_name,
            'TRIGGER' as object_type,
            pg_get_triggerdef(t.oid, true) as definition,
            obj_description(t.oid, 'pg_trigger') as description
        FROM pg_catalog.pg_trigger t
        JOIN pg_catalog.pg_class c ON t.tgrelid = c.oid
        JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
        WHERE t.tgname ILIKE %s
        AND n.nspname = %s
        AND n.nspname NOT IN ('pg_catalog', 'information_schema')
        AND NOT t.tgisinternal
    """,

    'sequence': """
        SELECT 
            n.nspname || '.' || c.relname as object_name,
            'SEQUENCE' as object_type,
            format(
                'CREATE SEQUENCE %I.%I\n    INCREMENT %s\n    MINVALUE %s\n    MAXVALUE %s\n    START %s\n    CACHE %s%s;',
                n.nspname,
                c.relname,
                s.seqincrement,
                s.seqmin,
                s.seqmax,
                s.seqstart,
                s.seqcache,
                CASE WHEN s.seqcycle THEN '\n    CYCLE' ELSE '' END
            ) as definition,
            obj_description(c.oid, 'pg_class') as description
        FROM pg_catalog.pg_sequence s
        JOIN pg_catalog.pg_class c ON s.seqrelid = c.oid
        JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
        WHERE c.relname ILIKE %s
        AND n.nspname = %s
        AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    """,

    'index': """
        SELECT 
            n.nspname || '.' || c.relname as object_name,
            'INDEX' as object_type,
            pg_get_indexdef(i.indexrelid) as definition,
            obj_description(i.indexrelid, 'pg_class') as description
        FROM pg_catalog.pg_index i
        JOIN pg_catalog.pg_class c ON i.indexrelid = c.oid
        JOIN pg_catalog.pg_namespace n ON c.relnamespace = n.oid
        WHERE c.relname ILIKE %s
        AND n.nspname = %s
        AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    """
}

def extract_database_object_ddl(secret_name, object_type, object_name=None, object_schema=None):
    """
    Extract DDL and description for database objects
    
    Args:
        secret_name (str): The name of the secret containing database credentials
        object_type (str): Type of database object ('table', 'view', 'function', 'procedure', etc.)
        object_name (str, optional): Name of the object to search for
        object_schema (str, optional): Schema name to filter objects
    
    Returns:
        list: List of dictionaries containing object information
        str: Error message if no objects found
    """
    try:
        # Input validation
        if not object_name or not object_schema:
            raise ValueError("Both object_name and object_schema are required")

        # Validate object_type
        object_type_lower = object_type.lower()
        if object_type_lower not in queries:
            valid_types = ', '.join(queries.keys())
            raise ValueError(f"Invalid object_type: {object_type}. Valid types are: {valid_types}")

        # Connect to database
        conn = connect_to_db(secret_name)
        if not conn:
            raise Exception("Failed to establish database connection")

        results = []
        with conn.cursor() as cur:
            try:
                # Debug information
                print(f"\nExecuting query for {object_type_lower}")
                print(f"Object name: {object_name}")
                print(f"Schema: {object_schema}")

                # Get query and execute
                query = queries[object_type_lower]
                params = [object_name, object_schema]
                
                print("\nExecuting query with parameters:")
                print(f"Query: {query}")
                print(f"Parameters: {params}")

                cur.execute(query, params)
                
                # Fetch results
                rows = cur.fetchall()
                if not rows:
                    print("No rows returned from query")
                    return "No matching objects found"

                # Get column names
                columns = [desc[0] for desc in cur.description]
                print(f"\nColumns returned: {columns}")
                print(f"Number of rows: {len(rows)}")

                # Process results
                for row in rows:
                    if not row:
                        continue

                    # Create result dictionary
                    result = {}
                    for i, column in enumerate(columns):
                        result[column] = row[i] if i < len(row) else None

                    # Add explanation based on object type
                    if result.get('definition'):
                        if object_type_lower == 'table':
                            result['explanation'] = analyze_table_definition(result['definition'])
                        elif object_type_lower == 'view':
                            result['explanation'] = analyze_view_definition(result['definition'])
                        elif object_type_lower in ('function', 'procedure'):
                            result['explanation'] = analyze_routine_definition(result['definition'])
                        elif object_type_lower == 'trigger':
                            result['explanation'] = analyze_trigger_definition(result['definition'])
                        else:
                            result['explanation'] = f"DDL for {object_type_lower}"

                    results.append(result)
                    print(f"\nProcessed {object_type_lower}: {result.get('object_name', 'unknown')}")

            except Exception as e:
                error_msg = f"Error executing query: {str(e)}"
                print(f"\nError details:")
                print(f"Query: {query}")
                print(f"Parameters: {params}")
                print(f"Error message: {error_msg}")
                raise

        # Return results
        if not results:
            return "No matching objects found"

        print(f"\nSuccessfully retrieved {len(results)} objects")
        return results

    except Exception as e:
        error_msg = f"Failed to extract database object DDL: {str(e)}"
        print(f"\nError: {error_msg}")
        raise

    finally:
        if conn:
            try:
                conn.close()
                print("\nDatabase connection closed")
            except Exception as e:
                print(f"\nError closing connection: {str(e)}")


def analyze_table_definition(definition):
    """Analyze table DDL and return explanatory notes"""
    explanation = ["This table contains the following structure:"]
    
    # Extract column definitions
    columns = []
    for line in definition.split('\n'):
        if 'CREATE TABLE' not in line and '(' not in line and ')' not in line:
            if line.strip():
                columns.append(line.strip())

    # Analyze columns
    for column in columns:
        if column.endswith(','):
            column = column[:-1]
        parts = column.split()
        if len(parts) >= 2:
            col_name = parts[0]
            col_type = parts[1]
            constraints = ' '.join(parts[2:])
            explanation.append(f"- {col_name}: {col_type} {constraints}")

    return '\n'.join(explanation)

def generate_object_explanation(obj_info):
    """
    Generate a human-readable explanation of the database object
    
    Args:
        obj_info (dict): Dictionary containing object information
    
    Returns:
        str: Human-readable explanation of the object
    """
    try:
        definition = obj_info.get('definition', '')
        obj_type = obj_info.get('object_type', '')
        explanation = []

        # Add object description if available
        description = obj_info.get('description', '')
        if description:
            explanation.append(f"Description: {description}")

        # Analyze based on object type
        if obj_type == 'TABLE':
            explanation.extend(analyze_table_definition(definition))
        elif obj_type == 'VIEW':
            explanation.extend(analyze_view_definition(definition))
        elif obj_type in ('FUNCTION', 'PROCEDURE'):
            explanation.extend(analyze_routine_definition(definition))

        return '\n'.join(explanation) if explanation else "No explanation available"

    except Exception as e:
        print(f"Error generating explanation: {str(e)}")
        return "Error generating explanation"


def analyze_view_definition(definition):
    """Analyze view DDL and return explanatory notes"""
    explanation = ["This view represents the following:"]
    
    # Clean up the definition
    clean_def = definition.replace('\n', ' ').strip()
    
    # Extract main components
    if 'SELECT' in clean_def:
        explanation.append("This view performs a SELECT operation with the following characteristics:")
        
        # Analyze SELECT clause
        if 'JOIN' in clean_def:
            explanation.append("- Joins multiple tables")
        if 'WHERE' in clean_def:
            explanation.append("- Applies filtering conditions")
        if 'GROUP BY' in clean_def:
            explanation.append("- Aggregates data")
        if 'HAVING' in clean_def:
            explanation.append("- Applies post-aggregation filters")
        if 'ORDER BY' in clean_def:
            explanation.append("- Sorts the results")
        if 'UNION' in clean_def:
            explanation.append("- Combines multiple result sets")
        if 'WITH' in clean_def:
            explanation.append("- Uses Common Table Expressions (CTEs)")

    return '\n'.join(explanation)

def analyze_routine_definition(definition):
    """Analyze function/procedure DDL and return explanatory notes"""
    explanation = []
    
    # Determine if it's a function or procedure
    if 'FUNCTION' in definition:
        explanation.append("This is a function that:")
    else:
        explanation.append("This is a procedure that:")

    # Extract parameters
    if '(' in definition:
        param_section = definition[definition.find('(')+1:definition.find(')')]
        params = param_section.split(',')
        if params and params[0].strip():
            explanation.append("\nParameters:")
            for param in params:
                explanation.append(f"- {param.strip()}")

    # Identify return type for functions
    if 'RETURNS' in definition:
        return_type = definition[definition.find('RETURNS')+7:].split()[0]
        explanation.append(f"\nReturns: {return_type}")

    # Analyze body
    if 'BEGIN' in definition:
        explanation.append("\nLogic overview:")
        if 'IF' in definition:
            explanation.append("- Contains conditional logic")
        if 'LOOP' in definition or 'WHILE' in definition:
            explanation.append("- Contains loops")
        if 'INSERT' in definition:
            explanation.append("- Performs data insertion")
        if 'UPDATE' in definition:
            explanation.append("- Performs data updates")
        if 'DELETE' in definition:
            explanation.append("- Performs data deletion")
        if 'SELECT' in definition:
            explanation.append("- Retrieves data")
        if 'EXCEPTION' in definition:
            explanation.append("- Includes error handling")

    return '\n'.join(explanation)

def analyze_trigger_definition(definition):
    """Analyze trigger DDL and return explanatory notes"""
    explanation = ["This trigger:"]
    
    if 'BEFORE' in definition:
        explanation.append("- Executes BEFORE the event")
    elif 'AFTER' in definition:
        explanation.append("- Executes AFTER the event")
    
    if 'INSERT' in definition:
        explanation.append("- Fires on INSERT")
    if 'UPDATE' in definition:
        explanation.append("- Fires on UPDATE")
    if 'DELETE' in definition:
        explanation.append("- Fires on DELETE")
    
    if 'FOR EACH ROW' in definition:
        explanation.append("- Executes for each affected row")
    elif 'FOR EACH STATEMENT' in definition:
        explanation.append("- Executes once per statement")

    return '\n'.join(explanation)


def clean_query_for_explain(query):
    """
    Remove any existing EXPLAIN or EXPLAIN ANALYZE keywords from the query
    
    Parameters:
    - query: Original query string
    Returns:
    - Cleaned query string
    """
    # Remove common EXPLAIN variants (case-insensitive)
    patterns = [
        r'^\s*EXPLAIN\s+ANALYZE\s+',
        r'^\s*EXPLAIN\s+\(.*?\)\s+',
        r'^\s*EXPLAIN\s+'
    ]
    
    cleaned_query = query
    for pattern in patterns:
        cleaned_query = re.sub(pattern, '', cleaned_query, flags=re.IGNORECASE)
    
    return cleaned_query.strip()

def analyze_query_performance(secret_name, query_or_object_name, parameters=None, object_type=None):
    """
    Analyze query performance and provide optimization recommendations
    
    Parameters:
    - secret_name: Secret containing database credentials
    - query_or_object_name: SQL query string or object name to analyze
    - parameters: Optional. List of parameter values for parameterized queries
    - object_type: Optional. If provided, will fetch definition from database object
    """
    conn = connect_to_db(secret_name)
    try:
        with conn.cursor() as cur:
            # If object_type is provided, fetch the query definition
            if object_type:
                query_to_analyze = get_object_definition(cur, query_or_object_name, object_type)
            else:
                query_to_analyze = query_or_object_name

            # Clean the query before analysis
            query_to_analyze = clean_query_for_explain(query_to_analyze)

            # Check if the query contains parameter placeholders
            has_parameters = any(f'${i}' in query_to_analyze for i in range(1, 21))

            if has_parameters:
                # Replace $n parameters with dummy placeholders
                modified_query = query_to_analyze
                param_count = 0
                for i in range(1, 21):
                    if f'${i}' in modified_query:
                        param_count = max(param_count, i)
                        modified_query = modified_query.replace(f'${i}', 'NULL')

                # Use GENERIC_PLAN for parameterized queries
                cur.execute(f"EXPLAIN (GENERIC_PLAN, BUFFERS, FORMAT JSON) {modified_query}")
                plan = cur.fetchone()[0]

                cur.execute(f"EXPLAIN (FORMAT JSON) {modified_query}")
                estimated_plan = cur.fetchone()[0]
                
                # Pass True for is_generic_plan
                analysis = analyze_execution_plan(plan[0], estimated_plan[0], True)
            else:
                # For non-parameterized queries, use ANALYZE
                cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query_to_analyze}")
                plan = cur.fetchone()[0]
                
                cur.execute(f"EXPLAIN (FORMAT JSON) {query_to_analyze}")
                estimated_plan = cur.fetchone()[0]
                
                # Pass False for is_generic_plan
                analysis = analyze_execution_plan(plan[0], estimated_plan[0], False)

            return analysis

    except Exception as e:
        raise Exception(f"Failed to analyze query performance: {str(e)}")
    finally:
        if conn:
            conn.close()

def analyze_execution_plan(actual_plan, estimated_plan, is_generic_plan):
    """
    Analyze execution plan and provide detailed explanations and recommendations
    """
    analysis = {
        'summary': [],
        'issues': [],
        'recommendations': [],
        'performance_stats': {}
    }

    analysis['plan_type'] = 'Generic Plan' if is_generic_plan else 'Analyzed Plan'

    # Extract key performance metrics
    total_cost = actual_plan['Plan'].get('Total Cost')
    rows = actual_plan['Plan'].get('Plan Rows')  # Use Plan Rows for generic plans
    estimated_rows = estimated_plan['Plan'].get('Plan Rows')
    
    # Initialize performance stats
    performance_stats = {
        'total_cost': total_cost,
        'estimated_rows': estimated_rows,
        'plan_rows': rows
    }

    # Add actual execution metrics only for analyzed plans
    if not is_generic_plan:
        actual_time = actual_plan['Plan'].get('Actual Total Time')
        actual_rows = actual_plan['Plan'].get('Actual Rows')
        performance_stats.update({
            'execution_time_ms': actual_time,
            'actual_rows': actual_rows
        })
    
    analysis['performance_stats'] = performance_stats

    # Analyze node types and operations
    analyze_plan_node(actual_plan['Plan'], analysis, is_generic_plan)
    
    # Check for common issues
    identify_performance_issues(actual_plan['Plan'], estimated_plan['Plan'], analysis, is_generic_plan)
    
    # Generate recommendations
    generate_recommendations(analysis)
    
    return analysis

def analyze_plan_node(node, analysis, is_generic_plan):
    """
    Recursively analyze each node in the execution plan
    """
    # Analyze current node
    node_type = node['Node Type']
    
    # Check for expensive operations with appropriate metrics based on plan type
    if node_type == 'Seq Scan':
        analysis['issues'].append({
            'type': 'sequential_scan',
            'description': f"Sequential scan detected on table {node.get('Relation Name')}",
            'severity': 'high'
        })
    
    elif node_type == 'Nested Loop':
        if is_generic_plan:
            if node.get('Plan Rows', 0) > 1000:
                analysis['issues'].append({
                    'type': 'nested_loop_large_dataset',
                    'description': "Nested loop join planned for large dataset",
                    'severity': 'medium'
                })
        else:
            if node.get('Actual Rows', 0) > 1000:
                analysis['issues'].append({
                    'type': 'nested_loop_large_dataset',
                    'description': "Nested loop join performed on large dataset",
                    'severity': 'medium'
                })
    
    elif node_type == 'Hash Join':
        rows_metric = node.get('Plan Rows' if is_generic_plan else 'Actual Rows', 0)
        if node.get('Hash Cond') and rows_metric > 10000:
            analysis['issues'].append({
                'type': 'large_hash_join',
                'description': "Large hash join operation detected",
                'severity': 'medium'
            })

    # Check for filter conditions
    if 'Filter' in node:
        analyze_filter_condition(node['Filter'], analysis)

    # Recursively analyze child nodes
    for child in node.get('Plans', []):
        analyze_plan_node(child, analysis, is_generic_plan)

def analyze_filter_condition(filter_condition, analysis):
    """
    Analyze filter conditions for potential optimization opportunities
    """
    filter_lower = filter_condition.lower()
    
    # Check for function calls in WHERE clause
    if '(' in filter_condition and ')' in filter_condition:
        analysis['issues'].append({
            'type': 'function_in_filter',
            'description': "Function call in WHERE clause may prevent index usage",
            'severity': 'medium'
        })
    
    # Check for LIKE operations
    if ' like ' in filter_lower and filter_lower.startswith('%'):
        analysis['issues'].append({
            'type': 'leading_wildcard',
            'description': "Leading wildcard in LIKE clause prevents index usage",
            'severity': 'medium'
        })

def identify_performance_issues(actual_node, estimated_node, analysis, is_generic_plan):
    """
    Identify performance issues by comparing actual vs estimated plans
    """
    if not is_generic_plan:
        # Row estimation analysis only for actual execution plans
        if estimated_node.get('Plan Rows', 0) > 0:
            estimation_ratio = actual_node.get('Actual Rows', 0) / estimated_node['Plan Rows']
            if estimation_ratio > 10 or estimation_ratio < 0.1:
                analysis['issues'].append({
                    'type': 'poor_statistics',
                    'description': f"Statistics may be outdated - row estimation is off by factor of {estimation_ratio:.1f}",
                    'severity': 'high'
                })

    # Parallel execution analysis (applies to both plan types)
    if actual_node.get('Workers Planned', 0) > 0 and actual_node.get('Workers Launched', 0) == 0:
        analysis['issues'].append({
            'type': 'parallel_execution_failed',
            'description': "Parallel execution was planned but not executed",
            'severity': 'medium'
        })

def generate_recommendations(analysis):
    """
    Generate specific recommendations based on identified issues
    """
    for issue in analysis['issues']:
        if issue['type'] == 'sequential_scan':
            analysis['recommendations'].append({
                'issue': 'Sequential Scan Detected',
                'recommendation': """
                Consider the following solutions:
                1. Create an index on the commonly queried columns
                2. Review WHERE clause conditions for index compatibility
                3. Ensure statistics are up to date with ANALYZE
                
                Example index creation:
                CREATE INDEX idx_name ON table_name (column_name);
                """
            })
        
        elif issue['type'] == 'poor_statistics':
            analysis['recommendations'].append({
                'issue': 'Statistics Mismatch',
                'recommendation': """
                Update statistics for more accurate query planning:
                1. Run ANALYZE on the affected tables
                2. Consider increasing statistics target:
                   ALTER TABLE table_name ALTER COLUMN column_name SET STATISTICS 1000;
                3. Review and possibly update auto_vacuum settings
                """
            })
        
        elif issue['type'] == 'function_in_filter':
            analysis['recommendations'].append({
                'issue': 'Function in WHERE Clause',
                'recommendation': """
                Optimize filter conditions:
                1. Remove function calls from WHERE clause
                2. Consider creating a computed column with an index
                3. Rewrite the condition to use direct column comparisons
                
                Example:
                Instead of: WHERE UPPER(column) = 'VALUE'
                Use: WHERE column = LOWER('VALUE')
                """
            })

def format_analysis_output(analysis):
    """
    Format the analysis results into human-readable text
    """
    output = []
    
    # Performance Statistics
    output.append("Query Performance Summary:")
    
    # Check if this is a generic plan
    is_generic_plan = analysis.get('plan_type') == 'Generic Plan'
    
    if is_generic_plan:
        # For generic plans, show estimated metrics
        output.append(f"- Plan Type: Generic Plan (Parameterized Query)")
        output.append(f"- Estimated Total Cost: {analysis['performance_stats'].get('total_cost', 'N/A')}")
        output.append(f"- Estimated Rows: {analysis['performance_stats'].get('estimated_rows', 'N/A')}")
        output.append(f"- Plan Rows: {analysis['performance_stats'].get('plan_rows', 'N/A')}")
    else:
        # For actual execution plans, show actual metrics
        output.append(f"- Plan Type: Analyzed Plan")
        output.append(f"- Execution Time: {analysis['performance_stats'].get('execution_time_ms', 'N/A'):.2f} ms")
        output.append(f"- Actual Rows: {analysis['performance_stats'].get('actual_rows', 'N/A')}")
        output.append(f"- Estimated Rows: {analysis['performance_stats'].get('estimated_rows', 'N/A')}")
    
    output.append("")

    # Issues
    if analysis['issues']:
        output.append("Identified Issues:")
        for issue in analysis['issues']:
            output.append(f"- {issue['description']} (Severity: {issue['severity']})")
        output.append("")

    # Recommendations
    if analysis['recommendations']:
        output.append("Recommendations:")
        for rec in analysis['recommendations']:
            output.append(f"Problem: {rec['issue']}")
            output.append(f"Solution: {rec['recommendation']}")
            output.append("")

    return "\n".join(output)

def monitor_query_performance(query, start_time, rows_returned):
    """
    Monitor query performance and suggest analysis if needed
    
    Args:
        query (str): Executed SQL query
        start_time (float): Query start timestamp
        rows_returned (int): Number of rows returned
    
    Returns:
        dict: Performance metrics and analysis suggestion
    """
    execution_time = time.time() - start_time
    metrics = {
        'query': query,
        'execution_time': execution_time,
        'rows_returned': rows_returned,
        'timestamp': datetime.utcnow().isoformat(),
        'needs_analysis': False,
        'performance_message': ''
    }
    
    # Define performance thresholds
    SLOW_QUERY_THRESHOLD = 5  # seconds
    HIGH_ROWS_THRESHOLD = 10000
    
    # Check for performance issues
    performance_issues = []
    
    if execution_time > SLOW_QUERY_THRESHOLD:
        performance_issues.append(f"Query took {execution_time:.2f} seconds to execute")
        metrics['needs_analysis'] = True
    
    if rows_returned > HIGH_ROWS_THRESHOLD:
        performance_issues.append(f"Query returned {rows_returned} rows")
        metrics['needs_analysis'] = True
    
    if metrics['needs_analysis']:
        metrics['performance_message'] = (
            "⚠️ Performance Warning:\n"
            f"{'; '.join(performance_issues)}.\n"
            "Would you like me to analyze this query for potential optimizations? "
            "Reply with 'yes' to get performance recommendations."
        )
        logger.warning(f"Slow query detected: {query}")
    else:
        metrics['performance_message'] = f"Query executed successfully in {execution_time:.2f} seconds"
    
    return metrics

def validate_query(query):
    """
    Validate query for security concerns and split into statements
    
    Args:
        query (str): SQL query to validate
    
    Returns:
        list: List of validated statements
        
    Raises:
        ValueError: If query contains prohibited operations
    """
    if not query or not isinstance(query, str):
        raise ValueError("Query must be a non-empty string")

    def is_within_quotes(text, position):
        """Check if a position in text is within quotes"""
        single_quotes = False
        double_quotes = False
        for i in range(position):
            if text[i] == "'" and not double_quotes:
                single_quotes = not single_quotes
            elif text[i] == '"' and not single_quotes:
                double_quotes = not double_quotes
        return single_quotes or double_quotes

    def split_statements(query_text):
        """Split query into individual statements, respecting quotes and comments"""
        statements = []
        current_stmt = []
        i = 0
        comment_block = False
        line_comment = False
        
        while i < len(query_text):
            char = query_text[i]
            
            # Handle comment blocks
            if query_text[i:i+2] == '/*' and not line_comment:
                comment_block = True
                current_stmt.append(char)
                i += 1
            elif query_text[i:i+2] == '*/' and comment_block:
                comment_block = False
                current_stmt.append(char)
                i += 1
            # Handle line comments
            elif query_text[i:i+2] == '--' and not comment_block:
                line_comment = True
                current_stmt.append(char)
                i += 1
            elif char == '\n' and line_comment:
                line_comment = False
                current_stmt.append(char)
            # Handle semicolons
            elif char == ';' and not comment_block and not line_comment and not is_within_quotes(query_text, i):
                current_stmt.append(char)
                stmt = ''.join(current_stmt).strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []
            else:
                current_stmt.append(char)
            i += 1
        
        # Add the last statement if exists
        last_stmt = ''.join(current_stmt).strip()
        if last_stmt:
            statements.append(last_stmt)
        
        return [stmt for stmt in statements if stmt]

    # Split into statements
    statements = split_statements(query)
    validated_statements = []

    # Validate each statement
    for stmt in statements:
        stmt = stmt.strip()
        if stmt.endswith(';'):
            stmt = stmt[:-1]
        
        stmt_lower = stmt.lower().strip()
        
        # Get the command type
        first_word = stmt_lower.split()[0] if stmt_lower.split() else ''
        
        if first_word not in ['select', 'show']:
            raise ValueError(f"Prohibited operation detected: {first_word}")
        
        # For SELECT statements, check for dangerous operations
        if first_word == 'select':
            dangerous_operations = [
                r'\binsert\b', r'\bupdate\b', r'\bdelete\b', r'\bdrop\b', 
                r'\btruncate\b', r'\balter\b', r'\bcreate\b', r'\bgrant\b', 
                r'\brevoke\b', r'\bexecute\b', r'\bcopy\b'
            ]
            
            # Remove content within quotes for checking
            query_for_check = ''
            in_quote = False
            quote_char = None
            
            for char in stmt:
                if char in ["'", '"'] and (not quote_char or char == quote_char):
                    if not in_quote:
                        quote_char = char
                        in_quote = True
                    else:
                        quote_char = None
                        in_quote = False
                elif not in_quote:
                    query_for_check += char
            
            # Check for dangerous operations
            for operation in dangerous_operations:
                if re.search(operation, query_for_check.lower()):
                    raise ValueError(f"Statement contains prohibited operation: {operation}")
        
        validated_statements.append(stmt)
    
    return validated_statements

def execute_read_query(secret_name, query, max_rows=20):
    """
    Execute read-only queries safely and return results with monitoring
    
    Args:
        secret_name (str): Secret containing database credentials
        query (str): SQL query to execute
        max_rows (int): Maximum number of rows to return (only for SELECT queries)
    
    Returns:
        dict: Query results and metadata
    """

    response = {
        'results': [],
        'performance_metrics': None,
        'warnings': [],
        'optimization_suggestions': []
    }
    
    start_time = time.time()
    conn = None
    
    try:
        # Validate and split queries
        statements = validate_query(query)
        
        # Connect to database
        conn = connect_to_db(secret_name)
        
        with conn.cursor() as cur:
            # Set session to read-only and timeout
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SET statement_timeout = '30s'")
            
            # Execute each statement
            for stmt_index, stmt in enumerate(statements, 1):
                stmt_response = {
                    'columns': [],
                    'rows': [],
                    'truncated': False,
                    'message': '',
                    'row_count': 0,
                    'query': stmt
                }
                
                # Determine if it's a SELECT query
                stmt_lower = stmt.lower().strip()
                is_select_query = stmt_lower.lstrip('(').startswith('select')
                
                # Prepare the final query
                final_query = stmt
                if is_select_query and 'limit' not in stmt_lower:
                    final_query = f"{stmt} LIMIT {max_rows + 1}"
                
                # Execute query
                try:
                    cur.execute(final_query)
                except psycopg2.Error as pe:
                    logger.error(f"Error executing query: {final_query}")
                    logger.error(f"Error details: {str(pe)}")
                    raise
                
                # Get column names
                stmt_response['columns'] = [desc[0] for desc in cur.description]
                
                # Fetch results
                rows = cur.fetchall()
                total_rows = len(rows)
                
                # Handle row limiting only for SELECT queries
                if is_select_query and total_rows > max_rows:
                    stmt_response['truncated'] = True
                    rows = rows[:max_rows]
                    stmt_response['message'] = (
                        f"Results truncated to {max_rows} rows for performance reasons. "
                        f"Total rows available: {total_rows}"
                    )
                    stmt_response['row_count'] = max_rows
                else:
                    stmt_response['row_count'] = total_rows
                
                # Convert rows to list of dictionaries
                stmt_response['rows'] = [
                    dict(zip(stmt_response['columns'], row))
                    for row in rows
                ]
                
                # Add performance monitoring only for SELECT queries
                if is_select_query:
                    complexity_metrics = analyze_query_complexity(stmt)
                    stmt_response['complexity_metrics'] = complexity_metrics
                    
                    # Add complexity warnings if any
                    if complexity_metrics['warnings']:
                        response['warnings'].extend(
                            f"Statement {stmt_index}: {warning}"
                            for warning in complexity_metrics['warnings']
                        )
                
                # Store the original query in the response
                stmt_response['query'] = f"{stmt};"
                response['results'].append(stmt_response)
            
            # Add overall performance metrics
            total_time = time.time() - start_time
            response['performance_metrics'] = {
                'execution_time': total_time,
                'statements_executed': len(statements),
                'timestamp': datetime.utcnow().isoformat(),
                'needs_analysis': total_time > 5,
                'performance_message': (
                    f"Executed {len(statements)} statements in {total_time:.2f} seconds"
                )
            }
            
            return response
                
    except ValueError as ve:
        error_msg = f"Query validation failed: {str(ve)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
        
    except psycopg2.Error as pe:
        error_msg = f"Database error: {str(pe)}"
        logger.error(error_msg)
        raise Exception(error_msg)
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    finally:
        if conn:
            conn.close()

def format_enhanced_results(results):
    """
    Format results with enhanced information
    """
    formatted_output = []
    
    # Add performance summary
    metrics = results['performance_metrics']
    formatted_output.append("Query Execution Summary:")
    formatted_output.append(f"- Total execution time: {metrics['execution_time']:.2f} seconds")
    formatted_output.append(f"- Statements executed: {metrics['statements_executed']}")
    formatted_output.append(f"- Total rows returned: {metrics['total_rows']}")
    formatted_output.append("")
    
    # Add warnings if any
    if results['warnings']:
        formatted_output.append("Warnings:")
        for warning in results['warnings']:
            formatted_output.append(f"- {warning}")
        formatted_output.append("")
    
    # Add optimization suggestions if any
    if results['optimization_suggestions']:
        formatted_output.append("Optimization Suggestions:")
        for suggestion in results['optimization_suggestions']:
            formatted_output.append(f"- {suggestion}")
        formatted_output.append("")
    
    # Format each statement's results
    for i, result in enumerate(results['results'], 1):
        formatted_output.append(f"Statement {i}:")
        formatted_output.append(f"Query: {result['query']}")
        
        # Add complexity metrics
        complexity = result['complexity_metrics']
        formatted_output.append("Complexity Analysis:")
        formatted_output.append(f"- Score: {complexity['complexity_score']}")
        formatted_output.append(f"- Joins: {complexity['join_count']}")
        formatted_output.append(f"- Subqueries: {complexity['subquery_count']}")
        formatted_output.append(f"- Aggregations: {complexity['aggregation_count']}")
        
        if result['message']:
            formatted_output.append(f"Note: {result['message']}")
        
        if result['columns']:
            # Calculate column widths
            widths = {
                col: max(len(str(col)), 
                        max(len(str(row[col])) for row in result['rows']))
                for col in result['columns']
            }
            
            # Add header
            header = " | ".join(
                str(col).ljust(widths[col])
                for col in result['columns']
            )
            formatted_output.append(header)
            formatted_output.append("-" * len(header))
            
            # Add rows
            for row in result['rows']:
                formatted_output.append(" | ".join(
                    str(row[col]).ljust(widths[col])
                    for col in result['columns']
                ))
            
        formatted_output.append(f"Rows returned: {result['row_count']}")
        formatted_output.append("")
    
    return "\n".join(formatted_output)

def format_query_results(results):
    """
    Format query results for display
    
    Args:
        results (dict): Query execution results
        
    Returns:
        str: Formatted results string
    """
    formatted_output = []
    
    # Add performance message first
    if results['performance_metrics'] and results['performance_metrics']['performance_message']:
        formatted_output.append(results['performance_metrics']['performance_message'] + "\n")
    
    # Add truncation message if applicable
    if results['message']:
        formatted_output.append(f"Note: {results['message']}\n")
    
    # Add column headers
    if results['columns']:
        # Calculate column widths
        widths = {}
        for col in results['columns']:
            widths[col] = len(str(col))
            for row in results['rows']:
                widths[col] = max(widths[col], len(str(row[col])))
        
        # Create header
        header = " | ".join(
            str(col).ljust(widths[col])
            for col in results['columns']
        )
        formatted_output.append(header)
        
        # Add separator
        separator = "-" * len(header)
        formatted_output.append(separator)
        
        # Add rows
        for row in results['rows']:
            formatted_row = " | ".join(
                str(row[col]).ljust(widths[col])
                for col in results['columns']
            )
            formatted_output.append(formatted_row)
    
    # Add summary
    formatted_output.append(f"\nTotal rows: {results['row_count']}")
    
    return "\n".join(formatted_output)

def format_multi_query_results(results):
    """Format results from multiple statements"""
    formatted_output = []
    
    # Add performance summary
    metrics = results['performance_metrics']
    formatted_output.append(f"Query Execution Summary:")
    formatted_output.append(f"- Total execution time: {metrics['execution_time']:.2f} seconds")
    formatted_output.append(f"- Statements executed: {metrics['statements_executed']}")
    formatted_output.append("")
    
    # Format each statement's results
    for i, result in enumerate(results['results'], 1):
        formatted_output.append(f"Statement {i}: {result['query']}")
        if result['message']:
            formatted_output.append(f"Note: {result['message']}")
        
        if result['columns']:
            # Calculate column widths
            widths = {
                col: max(len(str(col)), 
                        max(len(str(row[col])) for row in result['rows']))
                for col in result['columns']
            }
            
            # Add header
            header = " | ".join(
                str(col).ljust(widths[col])
                for col in result['columns']
            )
            formatted_output.append(header)
            formatted_output.append("-" * len(header))
            
            # Add rows
            for row in result['rows']:
                formatted_output.append(" | ".join(
                    str(row[col]).ljust(widths[col])
                    for col in result['columns']
                ))
            
        formatted_output.append(f"Rows returned: {result['row_count']}")
        formatted_output.append("")
    
    return "\n".join(formatted_output)

def execute_enhanced_query_diagnostics(secret_name, query):
    """
    Execute enhanced query diagnostics based on runbooks.py
    Provides comprehensive analysis including execution plan, performance metrics, and optimization suggestions
    """
    conn = None
    try:
        conn = connect_to_db(secret_name)
        results = {}
        
        with conn.cursor() as cur:
            # Get current database statistics
            cur.execute("""
                SELECT 
                    datname,
                    numbackends as active_connections,
                    xact_commit as total_commits,
                    xact_rollback as total_rollbacks,
                    blks_read,
                    blks_hit,
                    CASE WHEN (blks_read + blks_hit) > 0 THEN
                        ROUND(blks_hit::numeric / (blks_read + blks_hit) * 100, 2)
                    ELSE 0 END as cache_hit_ratio
                FROM pg_stat_database 
                WHERE datname = current_database();
            """)
            db_stats = cur.fetchone()
            if db_stats:
                results['database_stats'] = {
                    'database': db_stats[0],
                    'active_connections': db_stats[1],
                    'total_commits': db_stats[2],
                    'total_rollbacks': db_stats[3],
                    'blocks_read': db_stats[4],
                    'blocks_hit': db_stats[5],
                    'cache_hit_ratio': db_stats[6]
                }
            
            # Analyze the query execution plan
            try:
                cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}")
                plan_result = cur.fetchone()
                if plan_result:
                    plan = plan_result[0][0]
                    results['execution_plan'] = {
                        'total_cost': plan['Plan'].get('Total Cost'),
                        'execution_time': plan['Plan'].get('Actual Total Time'),
                        'rows_returned': plan['Plan'].get('Actual Rows'),
                        'node_type': plan['Plan'].get('Node Type'),
                        'startup_cost': plan['Plan'].get('Startup Cost')
                    }
                    
                    # Extract buffer usage if available
                    if 'Shared Hit Blocks' in plan['Plan']:
                        results['buffer_usage'] = {
                            'shared_hit_blocks': plan['Plan'].get('Shared Hit Blocks', 0),
                            'shared_read_blocks': plan['Plan'].get('Shared Read Blocks', 0),
                            'shared_dirtied_blocks': plan['Plan'].get('Shared Dirtied Blocks', 0),
                            'shared_written_blocks': plan['Plan'].get('Shared Written Blocks', 0)
                        }
            except Exception as e:
                results['execution_plan_error'] = str(e)
            
            # Get query from pg_stat_statements if available
            try:
                cur.execute("""
                    SELECT query, calls, total_exec_time, mean_exec_time, 
                           rows, shared_blks_hit, shared_blks_read
                    FROM pg_stat_statements 
                    WHERE query ILIKE %s
                    LIMIT 1;
                """, (f"%{query[:50]}%",))
                
                stmt_stats = cur.fetchone()
                if stmt_stats:
                    results['statement_stats'] = {
                        'calls': stmt_stats[1],
                        'total_exec_time': stmt_stats[2],
                        'mean_exec_time': stmt_stats[3],
                        'rows': stmt_stats[4],
                        'shared_blks_hit': stmt_stats[5],
                        'shared_blks_read': stmt_stats[6]
                    }
            except Exception as e:
                results['statement_stats_error'] = str(e)
        
        return results
        
    except Exception as e:
        raise Exception(f"Failed to execute enhanced query diagnostics: {str(e)}")
    finally:
        if conn:
            conn.close()

def execute_performance_insights_analysis(secret_name):
    """
    Execute performance analysis similar to AWS Performance Insights
    Based on runbooks.py diagnostic patterns
    """
    conn = None
    try:
        conn = connect_to_db(secret_name)
        results = {}
        
        with conn.cursor() as cur:
            # Top queries by execution time (similar to Performance Insights)
            cur.execute("""
                SELECT 
                    query,
                    calls,
                    total_exec_time/1000 as total_time_sec,
                    mean_exec_time/1000 as avg_time_sec,
                    (total_exec_time/sum(total_exec_time) OVER()) * 100 as pct_of_total_time,
                    rows,
                    shared_blks_hit,
                    shared_blks_read,
                    CASE WHEN (shared_blks_hit + shared_blks_read) > 0 THEN
                        ROUND(shared_blks_hit::numeric / (shared_blks_hit + shared_blks_read) * 100, 2)
                    ELSE 0 END as cache_hit_ratio
                FROM pg_stat_statements
                WHERE total_exec_time > 0
                ORDER BY total_exec_time DESC
                LIMIT 10;
            """)
            
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            results['top_queries_by_time'] = [dict(zip(columns, row)) for row in rows]
            
            # Wait events analysis (PostgreSQL equivalent)
            cur.execute("""
                SELECT 
                    wait_event_type,
                    wait_event,
                    COUNT(*) as count,
                    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
                FROM pg_stat_activity 
                WHERE wait_event_type IS NOT NULL
                GROUP BY wait_event_type, wait_event
                ORDER BY count DESC
                LIMIT 10;
            """)
            
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            results['wait_events'] = [dict(zip(columns, row)) for row in rows]
            
            # Database load metrics
            cur.execute("""
                SELECT 
                    COUNT(*) as total_connections,
                    COUNT(CASE WHEN state = 'active' THEN 1 END) as active_connections,
                    COUNT(CASE WHEN state = 'idle' THEN 1 END) as idle_connections,
                    COUNT(CASE WHEN state = 'idle in transaction' THEN 1 END) as idle_in_transaction,
                    AVG(EXTRACT(EPOCH FROM (now() - query_start))) as avg_query_duration_sec
                FROM pg_stat_activity
                WHERE backend_type = 'client backend';
            """)
            
            load_stats = cur.fetchone()
            if load_stats:
                results['database_load'] = {
                    'total_connections': load_stats[0],
                    'active_connections': load_stats[1],
                    'idle_connections': load_stats[2],
                    'idle_in_transaction': load_stats[3],
                    'avg_query_duration_sec': load_stats[4]
                }
        
        return results
        
    except Exception as e:
        raise Exception(f"Failed to execute performance insights analysis: {str(e)}")
    finally:
        if conn:
            conn.close()

def format_enhanced_diagnostics_output(results):
    """Format enhanced diagnostics results for display"""
    output = []
    
    if 'database_stats' in results:
        stats = results['database_stats']
        output.append("=== DATABASE STATISTICS ===")
        output.append(f"Database: {stats['database']}")
        output.append(f"Active Connections: {stats['active_connections']}")
        output.append(f"Cache Hit Ratio: {stats['cache_hit_ratio']}%")
        output.append(f"Total Commits: {stats['total_commits']}")
        output.append(f"Total Rollbacks: {stats['total_rollbacks']}")
        output.append("")
    
    if 'execution_plan' in results:
        plan = results['execution_plan']
        output.append("=== EXECUTION PLAN SUMMARY ===")
        output.append(f"Node Type: {plan['node_type']}")
        output.append(f"Execution Time: {plan['execution_time']:.2f} ms")
        output.append(f"Rows Returned: {plan['rows_returned']}")
        output.append(f"Total Cost: {plan['total_cost']:.2f}")
        output.append("")
    
    if 'buffer_usage' in results:
        buffer = results['buffer_usage']
        output.append("=== BUFFER USAGE ===")
        output.append(f"Shared Hit Blocks: {buffer['shared_hit_blocks']}")
        output.append(f"Shared Read Blocks: {buffer['shared_read_blocks']}")
        output.append(f"Shared Dirtied Blocks: {buffer['shared_dirtied_blocks']}")
        output.append("")
    
    if 'statement_stats' in results:
        stats = results['statement_stats']
        output.append("=== STATEMENT STATISTICS ===")
        output.append(f"Total Calls: {stats['calls']}")
        output.append(f"Mean Execution Time: {stats['mean_exec_time']:.2f} ms")
        output.append(f"Total Execution Time: {stats['total_exec_time']:.2f} ms")
        output.append(f"Average Rows: {stats['rows']}")
        output.append("")
    
    return "\n".join(output)

def lambda_handler(event, context):
    try:
        print(f"Received event: {json.dumps(event)}")
        
        # Check if arguments are nested under 'arguments' key
        if 'arguments' in event:
            # Extract arguments from the nested structure
            args = event['arguments']
            environment = args.get('environment')
            action_type = args.get('action_type')
        else:
            # Use the flat structure
            environment = event.get('environment')
            action_type = event.get('action_type')
        
        if not environment or not action_type:
            return {
                "functionResponse": {
                    "content": f"Error: Missing required parameters. Need 'environment' and 'action_type'."
                }
            }
            
        secret_name = get_env_secret(environment)
        min_exec_time = 1000

        # Get explain plan for a query
        if action_type == 'explain_query':
            query = event.get('query') if 'arguments' not in event else event['arguments'].get('query')
            print("Executing explain query scripts")
            results = analyze_query_performance(secret_name, query)
            formatted_results = format_analysis_output(results)
        elif action_type == 'extract_ddl':
            if 'arguments' in event:
                object_type = event['arguments'].get('object_type')
                object_name = event['arguments'].get('object_name')
                object_schema = event['arguments'].get('object_schema')
            else:
                object_type = event.get('object_type')
                object_name = event.get('object_name')
                object_schema = event.get('object_schema')
                
            print("Generating the DDL scripts for the object")
            results = extract_database_object_ddl(secret_name, object_type=object_type, object_name=object_name, object_schema=object_schema)
            # Convert results to string if it's not already
            formatted_results = str(results) if results else "No results found"
        elif action_type == 'execute_query':
            query = event.get('query') if 'arguments' not in event else event['arguments'].get('query')
            print("Executing read-only queries")
            results = validate_and_execute_queries(
                secret_name,
                query,
                max_rows=20,
                max_statements=5,
                max_total_rows=1000,
                max_complexity=15
            )
            formatted_results = format_enhanced_results(results)
        elif action_type == 'enhanced_query_diagnostics':
            query = event.get('query') if 'arguments' not in event else event['arguments'].get('query')
            print("Executing enhanced query diagnostics")
            results = execute_enhanced_query_diagnostics(secret_name, query)
            formatted_results = format_enhanced_diagnostics_output(results)
        elif action_type == 'performance_insights_analysis':
            print("Executing performance insights analysis")
            results = execute_performance_insights_analysis(secret_name)
            formatted_results = format_enhanced_results(results)
        else:
            print("I'm inside else condition")
            return {
                "functionResponse": {
                    "content": f"Error: Unknown action_type '{action_type}'. Available actions: explain_query, extract_ddl, execute_query, enhanced_query_diagnostics, performance_insights_analysis"
                }
            }

        # Format the response properly
        response_body = {
            'TEXT': {
                'body': formatted_results
            }
        }

        function_response = {
            'functionResponse': {
                'responseBody': response_body
            }
        }
        
        return function_response

    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")  # Add debugging
        return {
            "functionResponse": {
                "content": f"Error inside the exception block: {str(e)}"
            }
        }
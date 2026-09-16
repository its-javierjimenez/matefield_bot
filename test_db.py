import psycopg2

try:
    conn = psycopg2.connect(
        host="gamessao1079.bisecthosting.com",
        port=5432,
        user="u163006579_K9hF1DxFjM",
        password="vBZLroJdlUBLSDWZvByeWP4n",
        database="s163006579_matefield_dev"
    )
    print("Connection successful!")
    
    cur = conn.cursor()
    cur.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';")
    tables = cur.fetchall()
    print("Tables in db:")
    for t in tables:
        print(f"- {t[0]}")
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")

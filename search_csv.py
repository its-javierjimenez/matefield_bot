import csv
with open('d:/proyectos_dev/server_rcon_automation/docs/excel_history/VIP MATEFIELD - Registro VIP.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('ID DISCORD', '').strip() == '240644979393953792':
            print(f"Found in CSV: {row}")

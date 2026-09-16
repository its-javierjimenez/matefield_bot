import csv
with open('d:/proyectos_dev/server_rcon_automation/docs/excel_history/VIP MATEFIELD - Registro VIP.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        for k, v in row.items():
            if 'pendiente' in v.lower():
                print(f"Row {row.get('USUARIO')} has {k} = {v}")

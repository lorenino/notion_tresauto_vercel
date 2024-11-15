import sys
import pandas as pd
import requests
import json
import datetime

# Configuration : Token et ID de la base de données Notion
NOTION_TOKEN = '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'
DATABASE_ID = '13f7f7b5def5809eba81f50d5c1bd2f7'

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def check_database_properties():
    """Vérifier les propriétés disponibles dans la base de données"""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        properties = response.json()['properties']
        print("Propriétés dans la base de données Notion :")
        for prop_name, prop_info in properties.items():
            print(f"- {prop_name} ({prop_info['type']})")
    else:
        print(f"Erreur lors de la récupération des propriétés : {response.json()}")
        sys.exit(1)

def read_transactions(file_path):
    """Lire et nettoyer les transactions depuis un fichier Excel"""
    try:
        df = pd.read_excel(file_path, skiprows=9)
        df.columns = ['Date', 'Libellé', 'Débit euros', 'Crédits euros']
        df = df.dropna(how='all')
        df['Débit euros'] = df['Débit euros'].fillna(0).astype(float)
        df['Crédits euros'] = df['Crédits euros'].fillna(0).astype(float)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.strftime('%Y-%m-%d')
        df = df.dropna(subset=['Date'])
        return df
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier : {e}")
        sys.exit(1)

def get_existing_transactions():
    """Récupérer les transactions déjà présentes dans Notion"""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    existing_ids = set()
    has_more = True
    payload = {}
    while has_more:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        for result in data.get('results', []):
            props = result['properties']
            if 'Identifiant Transaction' in props and props['Identifiant Transaction']['rich_text']:
                trans_id = props['Identifiant Transaction']['rich_text'][0]['plain_text']
                existing_ids.add(trans_id)
        has_more = data.get('has_more', False)
        payload['start_cursor'] = data.get('next_cursor')
    return existing_ids

def add_transaction_to_notion(transaction):
    """Ajouter une nouvelle transaction dans Notion"""
    create_url = 'https://api.notion.com/v1/pages'
    new_page_data = {
        "parent": {"database_id": DATABASE_ID},
        "properties": {
            "Date": {"date": {"start": transaction['Date']}},
            "Libellé": {"title": [{"text": {"content": transaction['Libellé']}}]},
            "Débit euros": {"number": transaction['Débit euros']},
            "Crédits euros": {"number": transaction['Crédits euros']},  # Nom corrigé ici
            "Identifiant Transaction": {"rich_text": [{"text": {"content": transaction['Identifiant Transaction']}}]},
            "Justificatif Textuel": {"rich_text": [{"text": {"content": ""}}]},
            "Fichier de Facture": {"files": []}
        }
    }
    response = requests.post(create_url, headers=headers, json=new_page_data)
    if response.status_code == 200:
        print(f"Transaction ajoutée : {transaction['Libellé']}")
    else:
        print(f"Erreur lors de l'ajout : {response.text}")

def main(file_path):
    check_database_properties()  # Vérification des propriétés
    transactions = read_transactions(file_path)
    existing_transactions = get_existing_transactions()
    for _, row in transactions.iterrows():
        transaction_id = f"{row['Date']}_{row['Libellé']}_{row['Débit euros']}_{row['Crédits euros']}"
        if transaction_id not in existing_transactions:
            transaction = {
                'Date': row['Date'],
                'Libellé': row['Libellé'],
                'Débit euros': row['Débit euros'],
                'Crédits euros': row['Crédits euros'],
                'Identifiant Transaction': transaction_id
            }
            add_transaction_to_notion(transaction)
        else:
            print(f"Transaction déjà existante : {row['Libellé']}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <chemin_du_fichier_excel>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    main(file_path)

from flask import Flask, jsonify, request, render_template
import requests
import os
from datetime import datetime

app = Flask(__name__)

NOTION_TOKEN = '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'
DATABASE_ID = '13f7f7b5def5809eba81f50d5c1bd2f7'

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

UPLOAD_FOLDER = 'static/factures'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    """Page d'accueil pour afficher les transactions sans facture"""
    return render_template('index.html')

@app.route('/transactions', methods=['GET'])
def get_transactions():
    """Obtenir les transactions depuis Notion à partir de septembre"""
    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    transactions = []
    payload = {}
    has_more = True

    # Date limite (1er septembre de l'année en cours)
    date_limit = datetime(datetime.now().year, 9, 1)

    while has_more:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        for result in data.get('results', []):
            props = result['properties']
            transaction_date = props['Date']['date']['start'] if props['Date']['date'] else None
            if transaction_date:
                transaction_date_obj = datetime.strptime(transaction_date, '%Y-%m-%d')
                if transaction_date_obj >= date_limit:  # Filtrer les transactions après le 1er septembre
                    transaction = {
                        "id": result['id'],
                        "Date": transaction_date,
                        "Libellé": props['Libellé']['title'][0]['text']['content'],
                        "Débit euros": props['Débit euros']['number'],
                        "Crédits euros": props['Crédits euros']['number'],
                        "Fichier de Facture": props['Fichier de Facture']['files']
                    }
                    if not transaction["Fichier de Facture"]:  # Transactions sans facture
                        transactions.append(transaction)
        has_more = data.get('has_more', False)
        payload['start_cursor'] = data.get('next_cursor')

    return jsonify(transactions)

@app.route('/upload/<transaction_id>', methods=['POST'])
def upload_file(transaction_id):
    """Mettre à jour une transaction avec un fichier, en conservant l'extension d'origine"""
    file = request.files['file']
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # Extraire le nom de fichier et l'extension d'origine
    filename, file_extension = os.path.splitext(file.filename)
    saved_filename = f"facture_{transaction_id}_{datetime.now().strftime('%Y-%m-%d')}{file_extension}"
    filepath = os.path.join(UPLOAD_FOLDER, saved_filename)
    file.save(filepath)

    # Mise à jour de la transaction dans Notion avec le fichier téléversé
    url = f"https://api.notion.com/v1/pages/{transaction_id}"
    data = {
        "properties": {
            "Fichier de Facture": {
                "files": [
                    {
                        "name": saved_filename,
                        "external": {
                            "url": f"http://localhost:5000/{filepath}"  # URL pour accéder au fichier
                        }
                    }
                ]
            }
        }
    }
    response = requests.patch(url, headers=headers, json=data)
    if response.status_code == 200:
        return jsonify({"message": "Fichier ajouté avec succès"})
    else:
        return jsonify(response.json()), response.status_code

if __name__ == '__main__':
    app.run(debug=True)

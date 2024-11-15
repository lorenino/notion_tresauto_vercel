from flask import Flask, jsonify, request, render_template
import requests
from datetime import datetime
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)

# Récupérer les variables d'environnement pour Notion
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
DATABASE_ID = os.getenv('DATABASE_ID')

# Entêtes pour accéder à l'API Notion
headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

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
        
        # Débogage : Afficher la réponse complète de Notion
        print("Réponse de Notion:", data)
        
        if 'results' not in data:
            print("Erreur : 'results' non trouvé dans la réponse de Notion.")
            return jsonify({"error": "Erreur lors de la récupération des données de Notion"}), 500

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
    """Téléverser un fichier vers Transfer.sh et mettre à jour Notion avec le lien du fichier"""
    file = request.files['file']
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # Envoyer le fichier à Transfer.sh pour obtenir une URL temporaire
    response = requests.post('https://transfer.sh', files={'file': file})
    if response.status_code == 200:
        file_url = response.text.strip()

        # Mise à jour de la transaction dans Notion avec l'URL du fichier temporaire
        url = f"https://api.notion.com/v1/pages/{transaction_id}"
        data = {
            "properties": {
                "Fichier de Facture": {
                    "files": [
                        {
                            "name": file.filename,
                            "external": {
                                "url": file_url
                            }
                        }
                    ]
                }
            }
        }
        notion_response = requests.patch(url, headers=headers, json=data)
        if notion_response.status_code == 200:
            return jsonify({"message": "Fichier ajouté avec succès"})
        else:
            print("Erreur de Notion lors de la mise à jour :", notion_response.json())
            return jsonify(notion_response.json()), notion_response.status_code
    else:
        print("Erreur lors du téléversement du fichier vers Transfer.sh")
        return jsonify({"error": "Erreur lors du téléversement du fichier"}), response.status_code

if __name__ == '__main__':
    app.run(debug=True)

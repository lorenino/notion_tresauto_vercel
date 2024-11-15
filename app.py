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
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()  # Génère une exception pour les erreurs HTTP
            data = response.json()
            print("Réponse de Notion:", data)  # Debug : afficher la réponse de Notion
            
            if 'results' not in data:
                print("Erreur : 'results' non trouvé dans la réponse de Notion.")
                return jsonify({"error": "Erreur lors de la récupération des données de Notion"}), 500

            for result in data.get('results', []):
                props = result['properties']
                transaction_date = props['Date']['date']['start'] if props['Date']['date'] else None
                if transaction_date:
                    transaction_date_obj = datetime.strptime(transaction_date, '%Y-%m-%d')
                    if transaction_date_obj >= date_limit:
                        transaction = {
                            "id": result['id'],
                            "Date": transaction_date,
                            "Libellé": props['Libellé']['title'][0]['text']['content'],
                            "Débit euros": props['Débit euros']['number'],
                            "Crédits euros": props['Crédits euros']['number'],
                            "Fichier de Facture": props['Fichier de Facture']['files']
                        }
                        if not transaction["Fichier de Facture"]:
                            transactions.append(transaction)
            has_more = data.get('has_more', False)
            payload['start_cursor'] = data.get('next_cursor')
        except requests.exceptions.RequestException as e:
            print("Erreur de requête à Notion :", e)
            return jsonify({"error": "Erreur de connexion avec Notion"}), 500

    return jsonify(transactions)

@app.route('/upload/<transaction_id>', methods=['POST'])
def upload_file(transaction_id):
    """Téléverser un fichier vers File.io et mettre à jour Notion avec le lien du fichier"""
    file = request.files['file']
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    try:
        # Utilisation de File.io pour téléverser le fichier
        response = requests.post('https://file.io', files={'file': file})
        if response.status_code == 200:
            file_data = response.json()
            file_url = file_data.get('link')  # Récupérer le lien du fichier

            if not file_url:
                print("Erreur : Aucun lien de fichier retourné par File.io.")
                return jsonify({"error": "Erreur lors de la récupération de l'URL du fichier"}), 500

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
            print("Erreur lors du téléversement vers File.io :", response.status_code)
            return jsonify({"error": "Erreur lors du téléversement vers File.io"}), response.status_code
    except requests.exceptions.RequestException as e:
        print("Erreur lors de la connexion à File.io :", e)
        return jsonify({"error": "Erreur lors de la connexion à File.io"}), 500

if __name__ == '__main__':
    app.run(debug=True)

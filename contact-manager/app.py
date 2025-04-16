from flask import Flask, render_template, request, redirect, session, url_for
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
import qrcode
from io import BytesIO
import base64

app = Flask(__name__)
app.secret_key = "secret123"
bcrypt = Bcrypt(app)

client = MongoClient("mongodb://localhost:27017/")
db = client['contact_db']
users = db['users']
contacts = db['contacts']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')

        if users.find_one({"username": username}):
            return "User already exists!"

        users.insert_one({"username": username, "password": password})
        return redirect('/login')
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = users.find_one({"username": request.form['username']})
        if user and bcrypt.check_password_hash(user['password'], request.form['password']):
            session['username'] = user['username']
            return redirect('/dashboard')
        return "Invalid credentials"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect('/login')

    today = datetime.now().strftime('%m-%d')
    contact_list = contacts.find({"owner": session['username']})
    birthdays_today = contacts.find({
        "owner": session['username'],
        "dob": {"$regex": today}
    })
    return render_template('dashboard.html', contacts=contact_list, birthdays=birthdays_today)

@app.route('/add_contact', methods=['POST'])
def add_contact():
    if 'username' in session:
        name = request.form['name']
        phone = request.form['phone']
        dob = request.form['dob']  # format: YYYY-MM-DD

        contacts.insert_one({
            "name": name,
            "phone": phone,
            "dob": dob[5:],  # storing only MM-DD
            "owner": session['username']
        })
    return redirect('/dashboard')

@app.route('/search')
def search():
    if 'username' not in session:
        return redirect('/login')
    
    query = request.args.get('q', '')
    results = contacts.find({
        "owner": session['username'],
        "$or": [
            {"name": {"$regex": query, "$options": "i"}},
            {"phone": {"$regex": query}}
        ]
    })
    return render_template('dashboard.html', contacts=results, birthdays=[])

@app.route('/delete/<id>')
def delete_contact(id):
    if 'username' not in session:
        return redirect('/login')

    contacts.delete_one({"_id": ObjectId(id), "owner": session['username']})
    return redirect('/dashboard')

@app.route('/edit/<id>', methods=['GET'])
def edit_contact(id):
    if 'username' not in session:
        return redirect('/login')

    contact = contacts.find_one({"_id": ObjectId(id), "owner": session['username']})
    return render_template('edit.html', contact=contact)

@app.route('/update/<id>', methods=['POST'])
def update_contact(id):
    if 'username' not in session:
        return redirect('/login')

    name = request.form['name']
    phone = request.form['phone']
    dob = request.form['dob'][5:]

    contacts.update_one(
        {"_id": ObjectId(id), "owner": session['username']},
        {"$set": {"name": name, "phone": phone, "dob": dob}}
    )
    return redirect('/dashboard')

# ✅ QR Code with vCard format for contact import
@app.route('/qr/<id>')
def generate_qr(id):
    if 'username' not in session:
        return redirect('/login')

    contact = contacts.find_one({"_id": ObjectId(id), "owner": session['username']})
    if not contact:
        return "Contact not found", 404

    # ✅ Proper vCard format with structure
    vcard = f"""BEGIN:VCARD
VERSION:3.0
FN:{contact['name']}
N:{contact['name']};;;;
TEL;TYPE=CELL:{contact['phone']}
END:VCARD"""

    qr_img = qrcode.make(vcard)
    buffer = BytesIO()
    qr_img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f'''
    <html>
    <head>
        <title>QR Code for {contact['name']}</title>
    </head>
    <body style="text-align: center; font-family: sans-serif; background: #f0f0f0;">
        <h2>QR Code for {contact['name']}</h2>
        <img src="data:image/png;base64,{qr_base64}" alt="QR Code">
        <p>{contact['name']} - {contact['phone']}</p>
        <a href="/dashboard">⬅️ Back to Dashboard</a>
    </body>
    </html>
    '''


if __name__ == '__main__':
    app.run(debug=True)

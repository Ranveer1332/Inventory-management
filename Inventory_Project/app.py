from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
import threading
import queue
import time

app = Flask(__name__)
app.secret_key = 'chawla_super_secret_key' 

# --- RBAC LOGIN CREDENTIALS ---
USERS = {
    'owner': 'admin123',
    'cashier': 'cash123',
    'inventory': 'stock123'
}

# --- OS LEVEL ARCHITECTURE ---
RAM_BUFFER = queue.Queue(maxsize=50)
DB_MUTEX = threading.Lock()
BATCH_SIZE = 1

def init_db():
    with sqlite3.connect('chawla_enterprise.db') as conn:
        c = conn.cursor()
        
        # 1. Tables Create karna
        c.execute('''CREATE TABLE IF NOT EXISTS Products 
                     (id INTEGER PRIMARY KEY, name TEXT, retail_price REAL, wholesale_price REAL, stock INTEGER, supplier_id INTEGER)''')
                     
        c.execute('''CREATE TABLE IF NOT EXISTS Sales 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, barcode TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, scanned_by TEXT)''')
        
        # 2. THE MAGIC TRIGGER (Stock automatically minus karne ke liye)
        c.execute('''
            CREATE TRIGGER IF NOT EXISTS decrease_stock 
            AFTER INSERT ON Sales
            BEGIN
                UPDATE Products SET stock = stock - 1 WHERE id = NEW.barcode;
            END;
        ''')
        
        # 3. Dummy Data (Agar database khali hai)
        c.execute("SELECT COUNT(*) FROM Products")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO Products (id, name, retail_price, wholesale_price, stock, supplier_id) VALUES (12345, 'Navy Blue Blazer', 4500, 2500, 4, 101)")
            c.execute("INSERT INTO Products (id, name, retail_price, wholesale_price, stock, supplier_id) VALUES (67890, 'Black Tuxedo', 6000, 3500, 15, 102)")
        conn.commit()

# --- THE OS CONSUMER THREAD ---
def background_db_writer():
    while True:
        if RAM_BUFFER.qsize() >= BATCH_SIZE:
            items_to_save = []
            for _ in range(BATCH_SIZE):
                items_to_save.append((RAM_BUFFER.get(), 'cashier_session')) # Dummy session for now
            
            with DB_MUTEX:
                print(f"\n[OS LOG] Mutex Lock Acquired. Batch Writing...")
                time.sleep(1) # Simulating Slow I/O
                with sqlite3.connect('chawla_enterprise.db') as conn:
                    c = conn.cursor()
                    c.executemany("INSERT INTO Sales (barcode, scanned_by) VALUES (?, ?)", items_to_save)
                    conn.commit()
                print("[DBMS LOG] Batch Write Complete. Lock Released.\n")
        time.sleep(0.5)

threading.Thread(target=background_db_writer, daemon=True).start()

# --- GATEKEEPER (LOGIN/LOGOUT) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form['role']
        password = request.form['password']
        
        if role in USERS and USERS[role] == password:
            session['role'] = role
            if role == 'owner': return redirect(url_for('owner_dashboard'))
            elif role == 'cashier': return redirect(url_for('cashier_scanner'))
            elif role == 'inventory': return redirect(url_for('inventory_dashboard'))
        else:
            return render_template('login.html', error="Invalid Password! Access Denied.")
    return render_template('login.html', error=None)

@app.route('/logout')
def logout():
    session.pop('role', None)
    return redirect(url_for('login'))

# --- FRONTEND ROUTES ---
@app.route('/')
def cashier_scanner():
    if 'role' not in session or session['role'] != 'cashier': return redirect(url_for('login'))
    return render_template('scanner.html')

@app.route('/dashboard')
def owner_dashboard():
    if 'role' not in session or session['role'] != 'owner': return redirect(url_for('login'))
    with sqlite3.connect('chawla_enterprise.db') as conn:
        c = conn.cursor()
        c.execute("SELECT p.id, p.name, p.stock, p.retail_price, p.supplier_id, p.wholesale_price FROM Products p")
        data = c.fetchall()
    return render_template('dashboard.html', inventory=data)

@app.route('/inventory')
def inventory_dashboard():
    if 'role' not in session or session['role'] != 'inventory': return redirect(url_for('login'))
    with sqlite3.connect('chawla_enterprise.db') as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, stock, supplier_id FROM Products")
        data = c.fetchall()
    return render_template('inventory.html', inventory=data)

# --- APIs (THE ENGINE) ---
@app.route('/add_to_buffer', methods=['POST'])
def add_to_buffer():
    barcode = request.json.get('barcode')
    if not RAM_BUFFER.full():
        RAM_BUFFER.put(barcode)
        return jsonify({"status": "success", "buffer_size": RAM_BUFFER.qsize()})
    return jsonify({"status": "error"}), 503

@app.route('/get_product/<barcode>')
def get_product(barcode):
    with sqlite3.connect('chawla_enterprise.db') as conn:
        c = conn.cursor()
        c.execute("SELECT name, retail_price FROM Products WHERE id=?", (barcode,))
        item = c.fetchone()
        if item: return jsonify({"status": "success", "name": item[0], "price": item[1]})
        return jsonify({"status": "error", "name": "Unknown Item", "price": 0})

@app.route('/update_inventory', methods=['POST'])
def update_inventory():
    data = request.json
    
    # --- YAHAN FIX KIYA HAI (int lagaya hai) ---
    try:
        prod_id = int(data.get('id')) 
    except ValueError:
        return jsonify({"status": "error"}), 400
        
    name = data.get('name', 'Scanned Item')
    qty = int(data.get('qty', 1))
    supplier_id = int(data.get('supplier_id', 101))

    with sqlite3.connect('chawla_enterprise.db') as conn:
        c = conn.cursor()
        c.execute("SELECT stock FROM Products WHERE id=?", (prod_id,))
        if c.fetchone():
            c.execute("UPDATE Products SET stock = stock + ? WHERE id=?", (qty, prod_id))
            print(f"✅ [SUCCESS] Old Item Updated: ID {prod_id} | Added {qty} units")
        else:
            c.execute("INSERT INTO Products (id, name, retail_price, wholesale_price, stock, supplier_id) VALUES (?, ?, ?, ?, ?, ?)",
                      (prod_id, name, 2500, 1500, qty, supplier_id))
            print(f"✅ [SUCCESS] New Item Added: ID {prod_id} | Added {qty} units")
        conn.commit()
        
    return jsonify({"status": "success"})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5001, debug=True)
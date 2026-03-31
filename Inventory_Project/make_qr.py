import qrcode

# Tumhare database ke asli items aur unki Unique IDs
# Note: Value hamesha number format mein honi chahiye
inventory_items = {
    "Navy_Blue_Blazer": "12345",
    "Black_Tuxedo": "67890",
    "Cream_Sherwani": "45678",  # Jo tumne manual entry se add ki thi
    "New_Stock_Box": "88888"  
      # Godown mein auto-scan test karne ke liye
}

print("Starting Enterprise QR Generator...\n")

for item_name, item_id in inventory_items.items():
    # 1. QR Code ke andar SIRF ID (Number) feed kar rahe hain
    img = qrcode.make(item_id)
    
    # 2. File ka naam Insaan ke padhne layak bana rahe hain
    filename = f"{item_name}_ID_{item_id}.png"
    
    # 3. Image ko project folder mein save kar rahe hain
    img.save(filename)
    
    print(f"✅ Saved: {filename} (Hidden Data: {item_id})")

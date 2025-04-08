from app import db

def test_db_connection(app):
    with app.app_context():
        try:
            result = db.session.execute("SELECT 1").scalar()
            if result == 1:
                print("✅ Połączenie z bazą działa poprawnie.")
            else:
                print("⚠️ Niespodziewany wynik zapytania testowego.")
        except Exception as e:
            print("❌ Błąd połączenia z bazą danych:", e)


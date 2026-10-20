"""Diagnostic réseau : la machine arrive-t-elle à joindre Google en HTTPS ?

À lancer tel quel :  .venv\\Scripts\\python scripts\\test_reseau_google.py
Il ne touche à rien : il essaie juste d'ouvrir une connexion sécurisée vers
l'API Google Calendar et affiche précisément ce qui se passe."""

import socket
import ssl

HOTE = "www.googleapis.com"
PORT = 443


def tester():
    print(f"Test de connexion TLS vers {HOTE}:{PORT} ...\n")

    # 1) Simple connexion TCP (le port est-il atteignable ?)
    try:
        brute = socket.create_connection((HOTE, PORT), timeout=10)
    except Exception as e:
        print(f"[ÉCHEC] Impossible même d'ouvrir le port : {type(e).__name__} : {e}")
        print("        -> Un pare-feu bloque complètement la sortie. Réseau à changer.")
        return

    # 2) Poignée de main TLS (c'est là que ça cassait)
    contexte = ssl.create_default_context()
    try:
        with contexte.wrap_socket(brute, server_hostname=HOTE) as s:
            cert = s.getpeercert()
            emetteur = dict(x[0] for x in cert.get("issuer", []))
            print("[OK] Connexion sécurisée établie.")
            print(f"     Certificat émis par : {emetteur.get('organizationName', '?')}")
            print(f"     Version TLS : {s.version()}")
            print("\nSi l'émetteur n'est PAS Google (ex. un antivirus ou un proxy"
                  " d'entreprise), c'est lui qui intercepte le trafic.")
    except ssl.SSLError as e:
        print(f"[ÉCHEC TLS] {type(e).__name__} : {e}")
        print("        -> Un antivirus / proxy / VPN casse le chiffrement.")
        print("        -> Teste sur un autre réseau (partage de connexion du téléphone).")
    except Exception as e:
        print(f"[ÉCHEC] {type(e).__name__} : {e}")
    finally:
        brute.close()


if __name__ == "__main__":
    tester()

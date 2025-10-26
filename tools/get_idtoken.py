# get_idtoken.py
from google_auth_oauthlib.flow import InstalledAppFlow

# Standard OIDC scopes; do not over-scope
SCOPES = ["openid", "email", "profile"]

def main():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", scopes=SCOPES)
    creds = flow.run_local_server(port=0)  # opens browser, handles redirect
    print("CLIENT_ID (GOOGLE_AUDIENCE):", creds.client_id)
    print("ID_TOKEN (GOOGLE_TEST_ID_TOKEN):", creds.id_token)

if __name__ == "__main__":
    main()

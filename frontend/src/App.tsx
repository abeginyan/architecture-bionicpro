import React from 'react';
import { ReactKeycloakProvider } from '@react-keycloak/web';
import Keycloak, { KeycloakConfig, KeycloakInitOptions } from 'keycloak-js';
import ReportPage from './components/ReportPage';

const keycloakConfig: KeycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL,
  realm: process.env.REACT_APP_KEYCLOAK_REALM||"",
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID||""
};

const keycloak = new Keycloak(keycloakConfig);

// Authorization Code flow with PKCE (S256). keycloak-js generates the
// code_verifier, sends code_challenge/code_challenge_method=S256 on the
// authorization request and the code_verifier on the token request.
// Tokens are kept in memory by keycloak-js (not localStorage).
const initOptions: KeycloakInitOptions = {
  pkceMethod: 'S256',
  checkLoginIframe: false
};

const App: React.FC = () => {
  return (
    <ReactKeycloakProvider authClient={keycloak} initOptions={initOptions}>
      <div className="App">
        <ReportPage />
      </div>
    </ReactKeycloakProvider>
  );
};

export default App;
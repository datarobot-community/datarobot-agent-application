import fs from 'fs';
import path from 'path';

export default async () => {
  const statePath = path.resolve('./e2e/storageState.json');
  const baseURL = process.env.WEB_URL || 'http://localhost:5173';
  const isLocalhost = baseURL.includes('localhost');

  if (fs.existsSync(statePath)) {
    fs.unlinkSync(statePath);
  }

  // Create empty storage state for localhost so main tests don't fail
  // when auth test skips (no login needed locally)
  if (isLocalhost) {
    fs.writeFileSync(statePath, JSON.stringify({ cookies: [], origins: [] }));
  }
};

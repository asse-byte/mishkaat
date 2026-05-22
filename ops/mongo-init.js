// =============================================================================
// MongoDB bootstrap — creates a scoped application user with readWrite ONLY on
// the Mishkaat DB. Root credentials should NEVER be used by the app.
// Runs once on first container start (when /data/db is empty).
// =============================================================================

const dbName = process.env.MONGO_INITDB_DATABASE || "quran_center";
const appUser = process.env.MONGO_APP_USER;
const appPassword = process.env.MONGO_APP_PASSWORD;

if (!appUser || !appPassword) {
  print("[mongo-init] MONGO_APP_USER / MONGO_APP_PASSWORD not set — skipping app user creation");
} else {
  db = db.getSiblingDB(dbName);
  db.createUser({
    user: appUser,
    pwd: appPassword,
    roles: [{ role: "readWrite", db: dbName }],
  });
  print(`[mongo-init] Created scoped user '${appUser}' on db '${dbName}'`);
}

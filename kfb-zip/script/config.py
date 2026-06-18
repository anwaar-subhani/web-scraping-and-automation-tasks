import os


def _load_project_env():
	"""Load environment variables from project-level .env file if present."""
	project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
	env_path = os.path.join(project_root, ".env")

	if not os.path.exists(env_path):
		return

	try:
		with open(env_path, "r", encoding="utf-8") as env_file:
			for raw_line in env_file:
				line = raw_line.strip()
				if not line or line.startswith("#") or "=" not in line:
					continue

				key, value = line.split("=", 1)
				key = key.strip()
				value = value.strip().strip('"').strip("'")

				if key and key not in os.environ:
					os.environ[key] = value
	except Exception:
		# Silent fail to keep backwards compatibility with previous behavior
		pass


_load_project_env()

# KFB Login Configuration
KFB_LOGIN_URL = os.getenv("KFB_LOGIN_URL", "https://kfb.my.site.com/cac/s/")
DEFAULT_USERNAME = os.getenv("KFB_DEFAULT_USERNAME", "")
DEFAULT_PASSWORD = os.getenv("KFB_DEFAULT_PASSWORD", "")

# Property Status Variables
KFB_STAGE_INSTALLED = False
PENDING_SIGNATURE = False

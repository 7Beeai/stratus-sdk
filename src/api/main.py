from src.api.auth import StratusAuthenticationSystem
from src.api.health import StratusHealthChecks
from src.api.monitoring import StratusMonitoring

# Instancia a aplicação principal
from src.api.stratus_app import stratus_app
app = stratus_app.app 
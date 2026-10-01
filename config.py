import json
import os

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".controle_nf_config.json")

DEFAULT_CONFIG = {
    "diretorio_principal": "P:\\ARQUIVOS COMPARTILHAVEIS\\bd_nf",
}


def carregar_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = DEFAULT_CONFIG.copy()
            cfg.update(data)
            return cfg
        except (json.JSONDecodeError, OSError):
            pass
    return DEFAULT_CONFIG.copy()


def salvar_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def obter_diretorio_principal():
    return carregar_config().get("diretorio_principal", "")


def definir_diretorio_principal(caminho):
    cfg = carregar_config()
    cfg["diretorio_principal"] = caminho
    salvar_config(cfg)

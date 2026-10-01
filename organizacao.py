import os
import re
import shutil
import unicodedata

EMPRESAS_PALAVRAS_CHAVE = {
    "formatec": "FORMATEC",
    "shiki": "SHIKI",
    "totalfs": "TOTALFS",
}

EMPRESAS = sorted(set(EMPRESAS_PALAVRAS_CHAVE.values()))

PASTA_DANFE = "DANFE"
PASTA_CANHOTOS = "Canhotos"
PASTA_PDF = "PDF"
PASTA_XML = "XML"

PREFIXOS = {
    "nota": "NF",
    "cte": "CTE",
    "canhoto": "CANHOTO",
    "comprovante": "COMPROVANTE",
}

CATEGORIAS_EM_DANFE = {"nota", "cte"}

def _simplificar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def identificar_empresa(*textos):
    for texto in textos:
        simples = _simplificar(texto)
        for chave, pasta in EMPRESAS_PALAVRAS_CHAVE.items():
            if chave in simples:
                return pasta
    return ""


def slugify(texto, tamanho_max=40):
    texto = texto or "SEM_NOME"
    texto = re.sub(r"[^\w\-]+", "_", texto, flags=re.UNICODE)
    texto = re.sub(r"_{2,}", "_", texto).strip("_")
    return (texto or "SEM_NOME")[:tamanho_max]


def caminho_absoluto(base, relativo):
    if not relativo:
        return ""
    return os.path.normpath(os.path.join(base, *relativo.replace("\\", "/").split("/")))


def pasta_destino(base, categoria, empresa, extensao):
    if categoria in CATEGORIAS_EM_DANFE:
        tipo = PASTA_XML if extensao.lower() == ".xml" else PASTA_PDF
        return [PASTA_DANFE, tipo, empresa]
    return [PASTA_CANHOTOS, empresa]


def caminho_disponivel(caminho):
    if not os.path.exists(caminho):
        return caminho
    raiz, ext = os.path.splitext(caminho)
    i = 1
    while os.path.exists(f"{raiz}_{i}{ext}"):
        i += 1
    return f"{raiz}_{i}{ext}"


def salvar_arquivo(base, origem, categoria, empresa, numero_nota, cliente):
    if not empresa:
        raise ValueError("Empresa não informada.")
    ext = os.path.splitext(origem)[1].lower() or ".pdf"
    partes = pasta_destino(base, categoria, empresa, ext)
    pasta = os.path.join(base, *partes)
    os.makedirs(pasta, exist_ok=True)
    nome = f"{PREFIXOS[categoria]}_{numero_nota}_{slugify(cliente)}{ext}"
    destino = caminho_disponivel(os.path.join(pasta, nome))
    shutil.move(origem, destino)
    return "/".join(partes + [os.path.basename(destino)])
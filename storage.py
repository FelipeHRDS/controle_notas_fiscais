import json
import os
import re
import time
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, date

INDEX_FILENAME = "notas_fiscais.json"
LOCK_FILENAME = "notas_fiscais.lock"

STATUS_EMITIDA = "EMITIDA"
STATUS_EM_ROTA = "EM ROTA"
STATUS_CONCLUIDA = "CONCLUIDA"
STATUS_CANCELADA = "CANCELADA"

STATUS_VALIDOS = [STATUS_EMITIDA, STATUS_EM_ROTA, STATUS_CONCLUIDA, STATUS_CANCELADA]

ENTREGA_CARRO_PROPRIO = "CARRO PROPRIO"
ENTREGA_TRANSPORTADORA = "TRANSPORTADORA"


def identificar_tipo_entrega(nome_transportadora):
    """Classifica o nome lido em transporta/xNome (ou corrigido no PDF)."""
    nome = normalizar_busca(nome_transportadora)
    if not nome:
        return ""
    return ENTREGA_CARRO_PROPRIO if nome == "oproprio" else ENTREGA_TRANSPORTADORA

CAMPOS_ANEXO = {
    "canhoto": "canhoto_arquivo",
    "cte": "cte_arquivo",
    "comprovante": "comprovante_arquivo",
}

DIAS_LIMITE_PENDENCIA = 3

def _index_path(diretorio):
    return os.path.join(diretorio, INDEX_FILENAME)


def carregar_notas(diretorio):
    if not diretorio or not os.path.isdir(diretorio):
        return []
    caminho = _index_path(diretorio)
    if not os.path.exists(caminho):
        return []
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            notas = json.load(f)
        if not isinstance(notas, list):
            raise ValueError("O índice de notas não contém uma lista.")
        return notas
    except (json.JSONDecodeError, ValueError) as erro:
        raise ValueError(f"Índice de notas inválido: {caminho}. Corrija ou restaure antes de gravar.") from erro


def _gravar(diretorio, notas):
    caminho = _index_path(diretorio)
    temporario = caminho + ".tmp"
    with open(temporario, "w", encoding="utf-8") as f:
        json.dump(notas, f, ensure_ascii=False, indent=2)
    os.replace(temporario, caminho)


@contextmanager
def _bloqueio(diretorio, timeout=10.0, obsoleto=30.0):
    caminho = os.path.join(diretorio, LOCK_FILENAME)
    inicio = time.time()
    while True:
        try:
            os.close(os.open(caminho, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except FileExistsError:
            try:  
                if time.time() - os.path.getmtime(caminho) > obsoleto:
                    os.remove(caminho)
                    continue
            except OSError:
                pass
            if time.time() - inicio > timeout:
                raise TimeoutError(
                    "Outro usuário está gravando no índice de notas. Tente novamente em instantes."
                )
            time.sleep(0.1)
    try:
        yield
    finally:
        try:
            os.remove(caminho)
        except OSError:
            pass


def _modificar(diretorio, funcao):
    """Lê o índice, aplica 'funcao(notas)' e grava, tudo sob trava."""
    with _bloqueio(diretorio):
        notas = carregar_notas(diretorio)
        resultado = funcao(notas)
        _gravar(diretorio, notas)
    return resultado


def nova_nota(arquivo, cliente, codigo_cliente, emissao, numero_nota, transportadora,
              empresa="", empresa_razao="", tipo_entrega="",
              canhoto_arquivo=None, cte_arquivo=None, comprovante_arquivo=None):
    return {
        "id": str(uuid.uuid4()),
        "arquivo": arquivo,                      
        "cliente": cliente,
        "codigo_cliente": codigo_cliente,
        "emissao": emissao,
        "numero_nota": numero_nota,
        "transportadora": transportadora,
        "empresa": empresa,                      
        "empresa_razao": empresa_razao,          
        "tipo_entrega": tipo_entrega,            
        "status": STATUS_EMITIDA,
        "data_status_emitida": date.today().isoformat(),
        "data_adicao": datetime.now().isoformat(timespec="seconds"),
        "canhoto_arquivo": canhoto_arquivo,
        "cte_arquivo": cte_arquivo,
        "comprovante_arquivo": comprovante_arquivo,
        "alerta_dispensado": False,
    }


def adicionar_nota(diretorio, nota):
    _modificar(diretorio, lambda notas: notas.append(nota))


def existe_nota(diretorio, numero_nota, empresa):
    return any(
        normalizar_busca(n.get("numero_nota", "")).lstrip("0") == normalizar_busca(numero_nota).lstrip("0")
        and n.get("empresa", "") == empresa
        for n in carregar_notas(diretorio)
    )


def atualizar_nota(diretorio, nota_id, **campos):
    def aplicar(notas):
        for n in notas:
            if n["id"] == nota_id:
                n.update(campos)
                break
    _modificar(diretorio, aplicar)


def obter_nota(diretorio, nota_id):
    for n in carregar_notas(diretorio):
        if n["id"] == nota_id:
            return n
    return None


def alterar_status(diretorio, nota_id, novo_status):
    def aplicar(notas):
        for n in notas:
            if n["id"] == nota_id:
                n["status"] = novo_status
                if novo_status == STATUS_EMITIDA:
                    n["data_status_emitida"] = date.today().isoformat()
                    n["alerta_dispensado"] = False
                break
    _modificar(diretorio, aplicar)


def marcar_alerta_dispensado(diretorio, nota_id):
    atualizar_nota(diretorio, nota_id, alerta_dispensado=True)

def dias_em_emitida(nota):
    if nota.get("status") != STATUS_EMITIDA:
        return 0
    try:
        d = date.fromisoformat(nota.get("data_status_emitida", date.today().isoformat()))
    except ValueError:
        return 0
    return (date.today() - d).days


def esta_pendente(nota):
    return nota.get("status") == STATUS_EMITIDA and dias_em_emitida(nota) > DIAS_LIMITE_PENDENCIA


def notas_pendentes(notas):
    return [n for n in notas if esta_pendente(n)]

def data_para_ordenacao(nota):
    """Data usada para ordenar por 'mais recente': a emissão (dd/mm/aaaa);
    se inválida, a data em que a nota foi adicionada ao sistema."""
    try:
        return datetime.strptime(nota.get("emissao", ""), "%d/%m/%Y")
    except (ValueError, TypeError):
        try:
            return datetime.fromisoformat(nota.get("data_adicao"))
        except (ValueError, TypeError):
            return datetime.min


def normalizar_busca(texto):
    """Remove acentos, deixa minúsculo e tira tudo que não é letra/número.
    Assim '61135', '61.135' ou '000.061.135' se encontram entre si."""
    if texto is None:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", texto.lower())


def nota_combina_com_busca(nota, termo):
    """Busca texto por trecho e números apenas no número da NF ou código do cliente."""
    palavras = [normalizar_busca(p) for p in str(termo).split()]
    palavras = [p for p in palavras if p]
    campos_texto = ("cliente", "transportadora", "empresa", "empresa_razao", "status")
    valores_texto = [normalizar_busca(nota.get(c, "")) for c in campos_texto]
    valores_numero = [normalizar_busca(nota.get(c, "")) for c in
                      ("numero_nota", "codigo_cliente")]

    for palavra in palavras:
        if palavra.isdigit():
            numero = palavra.lstrip("0") or "0"
            if not any(numero in (valor.lstrip("0") or "0") for valor in valores_numero if valor):
                return False
        elif not any(palavra in valor for valor in valores_texto + valores_numero):
            return False
    return True

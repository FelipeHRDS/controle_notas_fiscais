import re
import xml.etree.ElementTree as ET
from datetime import datetime


def _nome(elemento):
    return elemento.tag.rsplit('}', 1)[-1]


def _filho(elemento, nome):
    if elemento is not None:
        return next((filho for filho in elemento if _nome(filho) == nome), None)
    return None


def _texto(elemento, *caminho):
    for parte in caminho:
        elemento = _filho(elemento, parte)
    return (elemento.text or '').strip() if elemento is not None else ''


def _ler_nfe(caminho):
    raiz = ET.parse(caminho).getroot()
    nfe = next((el for el in raiz.iter() if _nome(el) == 'NFe'), None)
    inf = _filho(nfe, 'infNFe')
    if inf is None:
        raise ValueError('O arquivo não contém uma NF-e (NFe/infNFe).')
    return inf


def eh_xml_nfe(caminho):
    try:
        _ler_nfe(caminho)
        return True
    except (ET.ParseError, OSError, ValueError):
        return False


def extrair_campos_xml(caminho):
    inf = _ler_nfe(caminho)
    ide, dest, emit, transp = (_filho(inf, nome) for nome in ('ide', 'dest', 'emit', 'transp'))
    emissao = _texto(ide, 'dhEmi') or _texto(ide, 'dEmi')
    if emissao:
        try:
            emissao = datetime.fromisoformat(emissao.replace('Z', '+00:00')).strftime('%d/%m/%Y')
        except ValueError:
            emissao = ''
    adicionais = _texto(inf, 'infAdic', 'infCpl')
    codigo = re.search(r'\bCliente\s*:\s*([\w/-]+)', adicionais, re.IGNORECASE)
    return {
        'cliente': _texto(dest, 'xNome'),
        'codigo_cliente': codigo.group(1) if codigo else '',
        'emissao': emissao,
        'numero_nota': _texto(ide, 'nNF'),
        'transportadora': _texto(transp, 'transporta', 'xNome'),
        'empresa_razao': _texto(emit, 'xNome'),
    }

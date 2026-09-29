# -*- coding: utf-8 -*-
"""
Extração de campos de PDFs de Nota Fiscal (DANFE) usando pdfplumber + regex.

IMPORTANTE: o layout de DANFEs varia bastante entre emissores e sistemas de
origem (ERP). As expressões abaixo cobrem os padrões mais comuns de DANFE em
português, mas a extração é "melhor esforço": o programa sempre mostra uma
tela de confirmação com os campos editáveis antes de salvar a nota, para que
o operador corrija qualquer campo que não tenha sido lido corretamente.
"""
import re
import pdfplumber


def extrair_texto(caminho_pdf):
    texto = ""
    try:
        with pdfplumber.open(caminho_pdf) as pdf:
            for pagina in pdf.pages:
                t = pagina.extract_text()
                if t:
                    texto += t + "\n"
    except Exception:
        # PDF pode ser uma imagem escaneada sem texto, corrompido, etc.
        # Nesse caso devolvemos texto vazio e o operador preenche manualmente.
        pass
    return texto


def _buscar(padroes, texto, grupo=1):
    for padrao in padroes:
        m = re.search(padrao, texto, re.IGNORECASE)
        if m:
            valor = m.group(grupo).strip()
            valor = re.sub(r"\s{2,}", " ", valor)
            return valor
    return ""


# ---------------------------------------------------------------------------
# Padrões específicos do modelo de DANFE usado (ex.: notas da FORMATEC).
#
# Nesse modelo, quando o pdfplumber extrai o texto, os RÓTULOS dos campos
# (ex.: "NOME/RAZÃO SOCIAL", "DATA DA EMISSÃO") não saem no texto — só os
# valores, "achatados" em linhas. Por isso a extração aqui não procura por
# rótulo, e sim pelo FORMATO/POSIÇÃO de cada valor dentro da linha:
#
#   1) Linha do Destinatário (cliente):
#      "<NOME DO CLIENTE> <CNPJ do cliente> <DATA DE EMISSÃO>"
#      ex.: "BORRACHAS VIPAL S.A. 87.870.952/0014-69 17/09/2026"
#      -> cliente = "BORRACHAS VIPAL S.A.", emissão = "17/09/2026"
#
#   2) Linha da Transportadora:
#      "<NOME DA TRANSPORTADORA> [Destinatário|Remetente] <CNPJ>" (sem data
#      depois do CNPJ, ao contrário da linha do cliente)
#      ex.: "COTRAIBI COOP DOS TRANSPORTADORES Destinatário 07.441.985/0003-00"
#      -> transportadora = "COTRAIBI COOP DOS TRANSPORTADORES"
#
#   3) Número da nota: sempre no formato "Nº. 000.061.135"
#
#   4) Código do cliente: sempre em "Cliente: 88298-5" (Dados Adicionais)
# ---------------------------------------------------------------------------

_RE_CNPJ = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"

_PADRAO_CLIENTE_EMISSAO = re.compile(
    r"^(?P<nome>\S.*?)\s+" + _RE_CNPJ + r"\s+(?P<data>\d{2}/\d{2}/\d{4})\s*$"
)
_PADRAO_TRANSPORTADORA = re.compile(
    r"^(?P<nome>\S.*?)\s+(?:Destinat[áa]rio|Remetente)?\s*" + _RE_CNPJ + r"\s*$"
)


def _extrair_por_layout_danfe(texto):
    """Extração dedicada ao layout descrito acima. Devolve um dict; campos
    não encontrados ficam como string vazia."""
    cliente = emissao = transportadora = ""
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        if not cliente:
            m = _PADRAO_CLIENTE_EMISSAO.match(linha)
            if m:
                cliente = m.group("nome").strip()
                emissao = m.group("data")
                continue
        if not transportadora:
            m2 = _PADRAO_TRANSPORTADORA.match(linha)
            if m2:
                transportadora = m2.group("nome").strip()
        if cliente and transportadora:
            break

    numero_nota = _buscar([r"N[ºO°o]\.?\s*(\d{3}\.\d{3}\.\d{3})"], texto)
    codigo_cliente = _buscar([r"Cliente:\s*([\w\-/]+)"], texto)

    # Empresa emitente: todo DANFE começa com o texto do canhoto
    # "RECEBEMOS DE <EMPRESA> OS PRODUTOS CONSTANTES DA NOTA FISCAL..."
    empresa_razao = _buscar([r"RECEBEMOS\s+DE\s+(.+?)\s+OS\s+PRODUTOS"], texto)

    return {
        "cliente": cliente,
        "codigo_cliente": codigo_cliente,
        "emissao": emissao,
        "numero_nota": numero_nota,
        "transportadora": transportadora,
        "empresa_razao": empresa_razao,
    }


# Padrões genéricos (fallback), usados só nos campos que a extração acima
# não conseguir preencher — útil caso apareça, um dia, uma nota de outro
# layout em que os rótulos aparecem normalmente no texto extraído.
def _extrair_generico(texto):
    numero_nota = _buscar([
        r"N[ºO°o]\.?\s*(?:DA\s*)?(?:NF-?E?)?\s*[:\-]?\s*(\d{2,3}\.?\d{3}\.?\d{3})",
        r"NF-?E?\s*N[ºO°o]\.?\s*[:\-]?\s*(\d+)",
        r"N[úu]mero\s*[:\-]?\s*(\d{4,9})",
    ], texto)

    emissao = _buscar([
        r"DATA\s*DE\s*EMISS[ÃA]O\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        r"EMISS[ÃA]O\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
    ], texto)

    cliente = _buscar([
        r"DESTINAT[ÁA]RIO[^\n]*\n\s*NOME[/ ]*RAZ[ÃA]O SOCIAL\s*[:\-]?\s*([^\n]+)",
        r"NOME[/ ]*RAZ[ÃA]O SOCIAL\s*[:\-]?\s*([^\n]+)",
        r"CLIENTE\s*[:\-]?\s*([^\n]+)",
    ], texto)

    codigo_cliente = _buscar([
        r"C[ÓO]DIGO\s*DO\s*CLIENTE\s*[:\-]?\s*(\S+)",
        r"C[ÓO]D\.?\s*CLIENTE\s*[:\-]?\s*(\S+)",
        r"COD\.?\s*CLI\.?\s*[:\-]?\s*(\S+)",
    ], texto)

    transportadora = _buscar([
        r"TRANSPORTADORA\s*/?\s*VOLUMES?\s*TRANSPORTADOS?\s*[:\-]?\s*\n?\s*(?:NOME[/ ]*RAZ[ÃA]O SOCIAL\s*[:\-]?\s*)?([^\n]+)",
        r"TRANSPORTADORA\s*[:\-]?\s*([^\n]+)",
        r"RAZ[ÃA]O SOCIAL\s*\(TRANSPORTADORA\)\s*[:\-]?\s*([^\n]+)",
    ], texto)

    return {
        "cliente": cliente,
        "codigo_cliente": codigo_cliente,
        "emissao": emissao,
        "numero_nota": numero_nota,
        "transportadora": transportadora,
    }


def extrair_campos(caminho_pdf):
    texto = extrair_texto(caminho_pdf)

    campos = _extrair_por_layout_danfe(texto)
    if not all(campos[k] for k in
               ("cliente", "codigo_cliente", "emissao", "numero_nota", "transportadora")):
        genericos = _extrair_generico(texto)
        for chave, valor in genericos.items():
            if not campos.get(chave):
                campos[chave] = valor

    return campos

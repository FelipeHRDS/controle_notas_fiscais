# -*- coding: utf-8 -*-
"""Cadastro e anexos; o índice compartilhado é controlado por storage."""
import os
import shutil
import ntpath
import uuid

import organizacao
import storage

EXTENSOES = {
    'nota': {'.pdf', '.xml'},
    'canhoto': {'.pdf', '.png', '.jpg', '.jpeg', '.heic', '.webp'},
    'cte': {'.pdf', '.xml'},
    'comprovante': {'.pdf', '.xml'},
}


def _validar_arquivo(origem, categoria):
    if categoria not in EXTENSOES or os.path.splitext(origem)[1].lower() not in EXTENSOES[categoria]:
        raise ValueError(f'Tipo de arquivo inválido para {categoria}.')
    if not os.path.isfile(origem):
        raise ValueError(f'Arquivo não encontrado: {origem}')


def _transferir(base, origem, categoria, nota):
    _validar_arquivo(origem, categoria)
    return organizacao.salvar_arquivo(
        base, origem, categoria, nota['empresa'], nota['numero_nota'], nota['cliente'])


def cadastrar_nota(base, origem, dados):
    if dados.get('empresa') not in organizacao.EMPRESAS:
        raise ValueError('Selecione uma empresa cadastrada.')
    if dados.get('tipo_entrega') not in (storage.ENTREGA_CARRO_PROPRIO, storage.ENTREGA_TRANSPORTADORA):
        raise ValueError('Selecione o tipo de entrega.')
    if not dados.get('cliente') or not dados.get('numero_nota'):
        raise ValueError('Cliente e número da nota são obrigatórios.')
    _validar_arquivo(origem, 'nota')
    anexos = dados.get('anexos') or {}
    permitidos = {'canhoto'} if dados['tipo_entrega'] == storage.ENTREGA_CARRO_PROPRIO else set(storage.CAMPOS_ANEXO)
    for categoria in permitidos:
        if anexos.get(categoria):
            _validar_arquivo(anexos[categoria], categoria)
    fontes = [origem] + [anexos[c] for c in permitidos if anexos.get(c)]
    if len({os.path.normcase(os.path.abspath(f)) for f in fontes}) != len(fontes):
        raise ValueError('Selecione arquivos diferentes para a nota e cada anexo.')
    storage.carregar_notas(base)  # verifica o índice antes de mover qualquer arquivo
    nota = storage.nova_nota('', *(dados.get(campo, '') for campo in (
        'cliente', 'codigo_cliente', 'emissao', 'numero_nota', 'transportadora')),
        empresa=dados['empresa'], empresa_razao=dados.get('empresa_razao', ''),
        tipo_entrega=dados['tipo_entrega'])
    transferidos = []
    try:
        nota['arquivo'] = _transferir(base, origem, 'nota', nota)
        transferidos.append((origem, nota['arquivo']))
        for categoria in permitidos:
            if anexos.get(categoria):
                relativo = _transferir(base, anexos[categoria], categoria, nota)
                nota[storage.CAMPOS_ANEXO[categoria]] = relativo
                transferidos.append((anexos[categoria], relativo))
        storage.adicionar_nota(base, nota)
    except Exception as erro:
        falhas = []
        for original, relativo in reversed(transferidos):
            try:
                shutil.move(organizacao.caminho_absoluto(base, relativo), original)
            except OSError as falha:
                falhas.append(f"{original}: {falha}")
        if falhas:
            raise OSError(f"Falha no cadastro: {erro}. Não foi possível devolver: {'; '.join(falhas)}") from erro
        raise
    return nota


def anexar_arquivo(base, nota, categoria, origem):
    if categoria not in storage.CAMPOS_ANEXO:
        raise ValueError('Categoria de anexo inválida.')
    if categoria != 'canhoto' and nota.get('tipo_entrega') != storage.ENTREGA_TRANSPORTADORA:
        raise ValueError('Este anexo exige entrega por transportadora.')
    if nota.get('empresa') not in organizacao.EMPRESAS:
        raise ValueError('Defina uma empresa cadastrada antes de anexar.')
    _validar_arquivo(origem, categoria)
    storage.carregar_notas(base)  # verifica o índice antes de mover
    relativo = _transferir(base, origem, categoria, nota)
    try:
        storage.atualizar_nota(base, nota['id'], **{storage.CAMPOS_ANEXO[categoria]: relativo})
    except Exception as erro:
        try:
            shutil.move(organizacao.caminho_absoluto(base, relativo), origem)
        except OSError as falha:
            raise OSError(f"Falha ao anexar: {erro}. O arquivo permanece em {relativo}; devolução falhou: {falha}") from erro
        raise
    return relativo


# Uma exclusão envolve arquivos e índice; mantenha a trava durante toda a operação.
CAMPOS_ARQUIVO = ('arquivo', *storage.CAMPOS_ANEXO.values())


def excluir_nota(base, nota_id, numero_esperado, empresa_esperada):
    """Exclui a nota e os arquivos associados; devolve caminhos cuja limpeza falhou."""
    base_real = os.path.realpath(base)
    with storage._bloqueio(base):
        notas = storage.carregar_notas(base)
        nota = next((n for n in notas if n.get('id') == nota_id), None)
        if nota is None:
            raise ValueError('Esta nota já foi excluída. Atualize a lista.')
        if (nota.get('numero_nota'), nota.get('empresa')) != (numero_esperado, empresa_esperada):
            raise ValueError('Os dados da nota mudaram desde que esta janela foi aberta. Abra a nota novamente.')

        caminhos = []
        for campo in CAMPOS_ARQUIVO:
            relativo = nota.get(campo)
            if not relativo:
                continue
            # Dados antigos podem conter caminhos inválidos: nunca exclua fora da pasta base.
            if os.path.isabs(relativo) or ntpath.splitdrive(relativo)[0]:
                raise ValueError(f'Caminho inválido no campo {campo}: {relativo}')
            caminho_original = organizacao.caminho_absoluto(base, relativo)
            if os.path.islink(caminho_original):
                raise ValueError(f'Atalho simbólico no campo {campo}: {relativo}')
            caminho = os.path.realpath(caminho_original)
            if os.path.commonpath((base_real, caminho)) != base_real or caminho == base_real:
                raise ValueError(f'Arquivo fora do diretório base: {relativo}')
            if caminho in (os.path.realpath(storage._index_path(base)),
                           os.path.realpath(os.path.join(base, storage.LOCK_FILENAME))):
                raise ValueError(f'Caminho reservado no campo {campo}: {relativo}')
            if caminho not in caminhos:
                caminhos.append(caminho)

        usados = {
            os.path.realpath(organizacao.caminho_absoluto(base, outro.get(campo)))
            for outro in notas if outro.get('id') != nota_id
            for campo in CAMPOS_ARQUIVO if outro.get(campo)
        }
        if any(caminho in usados for caminho in caminhos):
            raise ValueError('Um arquivo desta nota também está associado a outra nota. Exclusão interrompida.')

        separados = []
        try:
            for caminho in caminhos:
                if not os.path.lexists(caminho):
                    continue
                if not os.path.isfile(caminho) or os.path.islink(caminho):
                    raise ValueError(f'O caminho associado não é um arquivo comum: {caminho}')
                temporario = caminho + '.exclusao-' + uuid.uuid4().hex
                os.replace(caminho, temporario)
                separados.append((caminho, temporario))
            storage._gravar(base, [n for n in notas if n.get('id') != nota_id])
        except Exception as erro:
            falhas = []
            for caminho, temporario in reversed(separados):
                try:
                    os.replace(temporario, caminho)
                except OSError as falha:
                    falhas.append(f'{temporario}: {falha}')
            if falhas:
                raise OSError(f'Exclusão interrompida: {erro}. Falha ao devolver arquivos: {"; ".join(falhas)}') from erro
            raise

        nao_removidos = []
        for _, temporario in separados:
            try:
                os.remove(temporario)
            except OSError:
                nao_removidos.append(temporario)
        return nao_removidos

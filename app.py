import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import config
import organizacao
import pdf_utils
import servico
import storage
import xml_utils


APP_TITLE = "Controle de Notas Fiscais"

CORES = {
    "fundo_janela": "#c9c400",        # fundo geral da janela e dos painéis
    "fundo_lista": "#736e00",         # moldura em volta da lista principal
    "destaque": "#6b6b00",            # botões de destaque (adicionar, salvar)
    "texto_sobre_destaque": "white",  # texto dentro dos botões de destaque
    "texto_sobre_fundo": "white",     # rótulos que ficam sobre o fundo da janela
    "texto_secundario": "#555555",    # textos de apoio/instrução
    "alerta": "#8a1f1f",              # título do alerta de notas pendentes
}

# Tipos de arquivo aceitos em cada seleção
FILTRO_NOTA = [("PDF ou XML", "*.pdf *.xml"), ("PDF", "*.pdf"), ("XML", "*.xml")]
FILTRO_CTE_COMPROVANTE = [("PDF ou XML", "*.pdf *.xml"), ("PDF", "*.pdf"), ("XML", "*.xml")]
FILTRO_CANHOTO = [("Foto ou PDF", "*.pdf *.png *.jpg *.jpeg *.heic *.webp"), ("Todos os arquivos", "*.*")]
FILTROS_ANEXO = {"canhoto": FILTRO_CANHOTO, "cte": FILTRO_CTE_COMPROVANTE, "comprovante": FILTRO_CTE_COMPROVANTE}

def rotulo_anexo(categoria, tipo_entrega):
    if categoria == "canhoto":
        if tipo_entrega == storage.ENTREGA_TRANSPORTADORA:
            return "Foto do canhoto assinado pelo motorista"
        if tipo_entrega == storage.ENTREGA_CARRO_PROPRIO:
            return "Canhoto assinado"
        return "Canhoto"
    return {"cte": "CTE (PDF ou XML)",
            "comprovante": "Comprovante de entrega assinado pelo cliente (PDF ou XML)"}[categoria]

# Função que deixa os botões de anexo visiveis de acordo com o tipo de entrega
def categorias_visiveis(tipo_entrega):
    if tipo_entrega == storage.ENTREGA_TRANSPORTADORA:
        return ["canhoto", "cte", "comprovante"]
    return ["canhoto"]


def abrir_arquivo_no_sistema(caminho, imprimir=False):
    try:
        os.startfile(caminho, "print" if imprimir else "open") 
    except Exception as e:
        messagebox.showerror("Erro ao abrir arquivo", str(e))

class DialogoNovaNota(tk.Toplevel):
    def __init__(self, master, origem, campos_iniciais, titulo_extra=None):
        super().__init__(master)
        titulo = "Confirmar dados da Nota Fiscal"
        if titulo_extra:
            titulo += f" ({titulo_extra})"
        self.title(titulo)
        self.resizable(False, False)
        self.resultado = None
        self.anexos = {c: None for c in storage.CAMPOS_ANEXO}
        self.grab_set()

        tk.Label(
            self, text=f"Arquivo da nota: {os.path.basename(origem)}", font=("TkDefaultFont", 9, "bold"),
        ).pack(padx=12, pady=(12, 0), anchor="w")
        tk.Label(
            self, text="Confira os dados lidos automaticamente e corrija o que for necessário:",
            fg=CORES["texto_secundario"],
        ).pack(padx=12, pady=(2, 6), anchor="w")

        campos = tk.Frame(self)
        campos.pack(padx=12, fill="x")
        self.vars = {}
        rotulos = [
            ("cliente", "Nome do Cliente"),
            ("codigo_cliente", "Código do Cliente"),
            ("emissao", "Data de Emissão (dd/mm/aaaa)"),
            ("numero_nota", "Número da Nota Fiscal"),
            ("transportadora", "Transportadora"),
        ]
        for i, (chave, rotulo) in enumerate(rotulos):
            tk.Label(campos, text=rotulo + ":").grid(row=i, column=0, sticky="e", padx=(0, 6), pady=3)
            var = tk.StringVar(value=campos_iniciais.get(chave, ""))
            tk.Entry(campos, textvariable=var, width=38).grid(row=i, column=1, sticky="w", pady=3)
            self.vars[chave] = var

        tk.Label(campos, text="Empresa:").grid(row=len(rotulos), column=0, sticky="e", padx=(0, 6), pady=3)
        empresa_detectada = organizacao.identificar_empresa(campos_iniciais.get("empresa_razao", ""))
        self.empresa_var = tk.StringVar(value=empresa_detectada)
        ttk.Combobox(
            campos, textvariable=self.empresa_var, values=organizacao.EMPRESAS, state="readonly", width=20,
        ).grid(row=len(rotulos), column=1, sticky="w", pady=3)
        razao = campos_iniciais.get("empresa_razao", "")
        if razao:
            tk.Label(campos, text=f"(emitente: {razao})", fg=CORES["texto_secundario"]).grid(
                row=len(rotulos) + 1, column=1, sticky="w")

        entrega = tk.LabelFrame(self, text="Tipo de entrega")
        entrega.pack(padx=12, pady=(10, 4), fill="x")
        self.tipo_var = tk.StringVar()
        tk.Label(entrega, textvariable=self.tipo_var).pack(anchor="w", padx=12, pady=6)

        self.anexos_frame = tk.LabelFrame(self, text="Anexos (opcionais — também dá para anexar depois)")
        self.anexos_frame.pack(padx=12, pady=4, fill="x")
        self.aviso_tipo = tk.Label(
            self.anexos_frame, text="Escolha o tipo de entrega para ver os anexos.", fg=CORES["texto_secundario"])
        self.linhas = {}
        for categoria in storage.CAMPOS_ANEXO:
            linha = tk.Frame(self.anexos_frame)
            rot_var = tk.StringVar()
            nome_var = tk.StringVar(value="nenhum arquivo")
            tk.Label(linha, textvariable=rot_var, anchor="w", width=40).pack(side="left")
            tk.Button(linha, text="Selecionar...", command=lambda c=categoria: self._selecionar(c)).pack(side="left", padx=4)
            tk.Label(linha, textvariable=nome_var, fg=CORES["texto_secundario"], anchor="w", width=26).pack(side="left")
            self.linhas[categoria] = (linha, rot_var, nome_var)
        self.vars["transportadora"].trace_add("write", lambda *_: self._atualizar_anexos())
        self._atualizar_anexos()

        botoes = tk.Frame(self)
        botoes.pack(pady=12)
        tk.Button(botoes, text="Cancelar", width=12, command=self._cancelar).pack(side="left", padx=6)
        tk.Button(botoes, text="Salvar Nota", width=14, command=self._confirmar,
                  bg=CORES["destaque"], fg=CORES["texto_sobre_destaque"]).pack(side="left", padx=6)
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

    def _atualizar_anexos(self):
        tipo = storage.identificar_tipo_entrega(self.vars["transportadora"].get())
        self.tipo_var.set(tipo or "Informe o nome da transportadora acima para identificar a entrega.")
        visiveis = categorias_visiveis(tipo) if tipo else []
        self.aviso_tipo.pack_forget()
        for categoria, (linha, rot_var, nome_var) in self.linhas.items():
            linha.pack_forget()
            if categoria not in visiveis:
                self.anexos[categoria] = None   
                nome_var.set("nenhum arquivo")
        if not visiveis:
            self.aviso_tipo.configure(text="Informe 'O PROPRIO' ou o nome da transportadora para ver os anexos.")
            self.aviso_tipo.pack(padx=8, pady=6, anchor="w")
            return
        for categoria in visiveis:
            linha, rot_var, _ = self.linhas[categoria]
            rot_var.set(rotulo_anexo(categoria, tipo) + ":")
            linha.pack(fill="x", padx=8, pady=3)

    def _selecionar(self, categoria):
        caminho = filedialog.askopenfilename(
            title=f"Selecione: {rotulo_anexo(categoria, storage.identificar_tipo_entrega(self.vars['transportadora'].get()))}",
            filetypes=FILTROS_ANEXO[categoria], parent=self,
        )
        if caminho:
            self.anexos[categoria] = caminho
            self.linhas[categoria][2].set(os.path.basename(caminho))

    def _confirmar(self):
        campos = {k: v.get().strip() for k, v in self.vars.items()}
        tipo = storage.identificar_tipo_entrega(campos["transportadora"])
        faltando = []
        if not campos["cliente"]:
            faltando.append("Nome do Cliente")
        if not campos["numero_nota"]:
            faltando.append("Número da Nota Fiscal")
        if not self.empresa_var.get():
            faltando.append("Empresa")
        if not tipo:
            faltando.append("Transportadora (use O PROPRIO para entrega própria)")
        if faltando:
            messagebox.showwarning("Dados incompletos", "Preencha: " + ", ".join(faltando) + ".", parent=self)
            return
        campos["empresa"] = self.empresa_var.get()
        campos["tipo_entrega"] = tipo
        campos["anexos"] = dict(self.anexos)
        self.resultado = campos
        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()

class DialogoDetalhesNota(tk.Toplevel):
    """Detalhes de uma nota: abrir/baixar/imprimir, anexos e status."""

    def __init__(self, master, app, nota):
        super().__init__(master)
        self.app = app
        self.nota = nota
        self.title(f"Nota Fiscal nº {nota.get('numero_nota', '')}")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._montar()

    @property
    def base(self):
        return self.app.diretorio

    def _caminho(self, campo):
        return organizacao.caminho_absoluto(self.base, self.nota.get(campo))

    def _montar(self):
        for w in self.winfo_children():
            w.destroy()
        nota = self.nota
        tipo = nota.get("tipo_entrega", "")

        info = (
            f"Empresa: {nota.get('empresa') or '(não definida)'}\n"
            f"Cliente: {nota.get('cliente','')}\n"
            f"Código do Cliente: {nota.get('codigo_cliente','')}\n"
            f"Emissão: {nota.get('emissao','')}\n"
            f"Número da NF: {nota.get('numero_nota','')}\n"
            f"Transportadora: {nota.get('transportadora','')}\n"
            f"Tipo de entrega: {tipo or '(não informado)'}"
        )
        tk.Label(self, text=info, justify="left", anchor="w").pack(fill="x", padx=14, pady=(14, 8))

        if not nota.get("empresa"):
            f = tk.LabelFrame(self, text="Empresa (necessária para guardar anexos)")
            f.pack(fill="x", padx=14, pady=6)
            self.empresa_var = tk.StringVar(value="")
            ttk.Combobox(f, textvariable=self.empresa_var, values=organizacao.EMPRESAS,
                         state="readonly", width=16).pack(side="left", padx=6, pady=8)
            tk.Button(f, text="Definir empresa", command=self._definir_empresa).pack(side="left", padx=6)

        acoes = tk.LabelFrame(self, text="Arquivo da Nota (PDF ou XML)")
        acoes.pack(fill="x", padx=14, pady=6)
        tk.Button(acoes, text="Visualizar", width=14, command=self._visualizar).pack(side="left", padx=6, pady=8)
        tk.Button(acoes, text="Baixar cópia", width=14, command=self._baixar).pack(side="left", padx=6, pady=8)
        tk.Button(acoes, text="Imprimir", width=14, command=self._imprimir).pack(side="left", padx=6, pady=8)

        anexos = tk.LabelFrame(self, text="Anexos")
        anexos.pack(fill="x", padx=14, pady=6)
        for i, categoria in enumerate(categorias_visiveis(tipo)):
            campo = storage.CAMPOS_ANEXO[categoria]
            anexado = bool(nota.get(campo))
            tk.Label(anexos, text=rotulo_anexo(categoria, tipo) + ":", anchor="w").grid(
                row=i, column=0, sticky="w", padx=6, pady=4)
            tk.Label(anexos, text="anexado" if anexado else "pendente",
                     fg="black" if anexado else CORES["alerta"], width=9).grid(row=i, column=1)
            tk.Button(anexos, text="Substituir" if anexado else "Anexar",
                      command=lambda c=categoria: self._anexar(c)).grid(row=i, column=2, padx=4)
            if anexado:
                tk.Button(anexos, text="Ver", command=lambda c=categoria: self._ver(c)).grid(row=i, column=3, padx=4)

        status_frame = tk.LabelFrame(self, text="Status de acompanhamento")
        status_frame.pack(fill="x", padx=14, pady=(6, 14))
        self.status_var = tk.StringVar(value=nota.get("status", storage.STATUS_EMITIDA))
        ttk.Combobox(status_frame, textvariable=self.status_var, values=storage.STATUS_VALIDOS,
                     state="readonly", width=16).pack(side="left", padx=6, pady=8)
        tk.Button(status_frame, text="Salvar status", command=self._salvar_status).pack(side="left", padx=6, pady=8)
        tk.Button(status_frame, text="Excluir nota e arquivos", command=self._excluir,
                  fg=CORES["alerta"]).pack(side="right", padx=6, pady=8)

    def _recarregar(self):
        atual = storage.obter_nota(self.base, self.nota["id"])
        if atual:
            self.nota = atual
        self.app.atualizar_lista()
        self._montar()

    def _definir_empresa(self):
        if not self.empresa_var.get():
            messagebox.showwarning("Empresa", "Escolha a empresa.", parent=self)
            return
        try:
            storage.atualizar_nota(self.base, self.nota["id"], empresa=self.empresa_var.get())
        except OSError as e:
            messagebox.showerror("Erro ao gravar", str(e), parent=self)
            return
        self._recarregar()

    def _arquivo_existente(self, campo, descricao):
        caminho = self._caminho(campo)
        if not caminho or not os.path.exists(caminho):
            messagebox.showerror("Arquivo não encontrado", f"{descricao} não foi encontrado no diretório.", parent=self)
            return None
        return caminho

    def _visualizar(self):
        caminho = self._arquivo_existente("arquivo", "O arquivo desta nota")
        if caminho:
            abrir_arquivo_no_sistema(caminho)

    def _ver(self, categoria):
        caminho = self._arquivo_existente(storage.CAMPOS_ANEXO[categoria], "O anexo")
        if caminho:
            abrir_arquivo_no_sistema(caminho)

    def _baixar(self):
        caminho = self._arquivo_existente("arquivo", "O arquivo desta nota")
        if not caminho:
            return
        ext = os.path.splitext(caminho)[1] or ".pdf"
        destino = filedialog.asksaveasfilename(
            title="Salvar cópia da nota fiscal", initialfile=os.path.basename(caminho),
            defaultextension=ext, filetypes=[(ext.upper().strip("."), f"*{ext}")], parent=self,
        )
        if destino:
            import shutil
            shutil.copy2(caminho, destino)
            messagebox.showinfo("Concluído", "Cópia salva com sucesso.", parent=self)

    def _imprimir(self):
        caminho = self._arquivo_existente("arquivo", "O arquivo desta nota")
        if not caminho:
            return
        if caminho.lower().endswith(".xml"):
            messagebox.showinfo(
                "Imprimir",
                "Este arquivo é um XML (não tem formatação para impressão). "
                "Imprima pelo PDF do DANFE, se você tiver um.", parent=self)
            return
        abrir_arquivo_no_sistema(caminho, imprimir=True)
        if not sys.platform.startswith("win"):
            messagebox.showinfo("Imprimir", "O PDF foi aberto no visualizador padrão; imprima por lá.", parent=self)

    def _anexar(self, categoria):
        """Anexa/substitui um arquivo. Devolve True se anexou."""
        if not self.nota.get("empresa"):
            messagebox.showwarning("Empresa", "Defina a empresa da nota antes de anexar arquivos.", parent=self)
            return False
        origem = filedialog.askopenfilename(
            title=f"Selecione: {rotulo_anexo(categoria, self.nota.get('tipo_entrega', ''))}",
            filetypes=FILTROS_ANEXO[categoria], parent=self,
        )
        if not origem:
            return False
        try:
            servico.anexar_arquivo(self.base, self.nota, categoria, origem)
        except (OSError, ValueError, TimeoutError) as e:
            messagebox.showerror("Erro ao anexar", str(e), parent=self)
            return False
        self._recarregar()
        return True

    def _excluir(self):
        numero = self.nota.get("numero_nota", "")
        empresa = self.nota.get("empresa", "")
        if not messagebox.askyesno(
            "Confirmar exclusão",
            f"Excluir definitivamente a nota {numero} da empresa {empresa or '(não definida)'}?\n\n"
            "A nota, o canhoto, o CTE e o comprovante associados serão removidos. "
            "Esta ação não pode ser desfeita.", parent=self,
        ):
            return
        try:
            pendentes = servico.excluir_nota(self.base, self.nota["id"], numero, empresa)
        except (OSError, ValueError, TimeoutError) as e:
            messagebox.showerror("Erro ao excluir", str(e), parent=self)
            self.app.atualizar_lista()
            return
        self.app.atualizar_lista()
        if pendentes:
            messagebox.showwarning(
                "Exclusão incompleta",
                "O registro foi removido, mas não foi possível apagar estes arquivos separados:\n"
                + "\n".join(pendentes), parent=self)
        else:
            messagebox.showinfo("Nota excluída", "A nota e seus arquivos foram excluídos.", parent=self)
        self.destroy()

    def _salvar_status(self):
        novo = self.status_var.get()
        if novo == storage.STATUS_CONCLUIDA and not self.nota.get("canhoto_arquivo"):
            if messagebox.askyesno(
                "Canhoto necessário",
                "Para concluir esta nota é preciso anexar o canhoto primeiro.\n"
                "Deseja selecionar o arquivo do canhoto agora?", parent=self,
            ) and self._anexar("canhoto"):
                self._aplicar_status(novo)
            return
        self._aplicar_status(novo)

    def _aplicar_status(self, novo):
        try:
            storage.alterar_status(self.base, self.nota["id"], novo)
        except OSError as e:
            messagebox.showerror("Erro ao gravar", str(e), parent=self)
            return
        messagebox.showinfo("Status atualizado", f"Status alterado para {novo}.", parent=self)
        self.app.atualizar_lista()
        self.destroy()

class DialogoAlertaPendencias(tk.Toplevel):
    """Alerta ao abrir o programa: notas em 'EMITIDA' há mais de 3 dias."""

    def __init__(self, master, app, pendentes):
        super().__init__(master)
        self.app = app
        self.title("Notas fiscais pendentes")
        self.resizable(False, False)
        self.grab_set()

        tk.Label(
            self, text="As notas abaixo estão como 'EMITIDA' há mais de 3 dias:",
            fg=CORES["alerta"], font=("TkDefaultFont", 10, "bold"),
        ).pack(padx=16, pady=(16, 6), anchor="w")

        self.checks = []
        lista = tk.Frame(self)
        lista.pack(padx=16, pady=4, fill="both")
        for nota in pendentes:
            var = tk.BooleanVar(value=False)
            texto = (f"NF {nota.get('numero_nota','')} - {nota.get('cliente','')} "
                     f"[{nota.get('empresa','')}] ({storage.dias_em_emitida(nota)} dias em EMITIDA)")
            tk.Checkbutton(lista, text=texto, variable=var, anchor="w", justify="left").pack(fill="x", anchor="w")
            self.checks.append((nota, var))

        tk.Label(self, text="Marque as notas que não deseja ver neste alerta novamente.",
                 fg=CORES["texto_secundario"]).pack(padx=16, pady=(8, 4), anchor="w")

        botoes = tk.Frame(self)
        botoes.pack(pady=12)
        tk.Button(botoes, text="Fechar", width=14, command=self.destroy).pack(side="left", padx=6)
        tk.Button(botoes, text="Aplicar e fechar", width=16, bg=CORES["destaque"],
                  fg=CORES["texto_sobre_destaque"], command=self._aplicar_e_fechar).pack(side="left", padx=6)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _aplicar_e_fechar(self):
        try:
            for nota, var in self.checks:
                if var.get():
                    storage.marcar_alerta_dispensado(self.app.diretorio, nota["id"])
        except OSError as e:
            messagebox.showerror("Erro ao gravar", str(e), parent=self)
            return
        self.app.atualizar_lista()
        self.destroy()

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x680")
        self.configure(bg=CORES["fundo_janela"])

        self.diretorio = config.obter_diretorio_principal()
        self.notas = []

        self._montar_interface()
        self.after(200, self._inicializar_diretorio_e_dados)

    def _inicializar_diretorio_e_dados(self):
        if not self.diretorio or not os.path.isdir(self.diretorio):
            self.escolher_diretorio(primeira_vez=True)
        else:
            self.atualizar_lista()
            self._checar_pendencias()

    def _montar_interface(self):
        fundo, claro = CORES["fundo_janela"], CORES["texto_sobre_fundo"]

        topo = tk.Frame(self, bg=fundo)
        topo.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(topo, text=APP_TITLE, bg=fundo, font=("TkDefaultFont", 14, "bold")).pack(side="left")

        busca = tk.Frame(self, bg=fundo)
        busca.pack(fill="x", padx=16, pady=6)

        tk.Label(busca, text="PESQUISAR", bg=fundo, fg=claro,
                 font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        self.busca_var = tk.StringVar()
        entry = tk.Entry(busca, textvariable=self.busca_var, width=34)
        entry.grid(row=1, column=0, sticky="w", pady=(2, 0))
        # busca em tempo real, a cada tecla digitada
        entry.bind("<KeyRelease>", lambda e: self.atualizar_lista())
        tk.Button(busca, text="Limpar", command=self._limpar_busca).grid(row=1, column=1, padx=6)

        def combo(coluna, rotulo, variavel, valores, largura):
            tk.Label(busca, text=rotulo, bg=fundo, fg=claro).grid(row=1, column=coluna, padx=(16, 4))
            c = ttk.Combobox(busca, textvariable=variavel, values=valores, state="readonly", width=largura)
            c.grid(row=1, column=coluna + 1)
            c.bind("<<ComboboxSelected>>", lambda e: self.atualizar_lista())

        self.filtro_empresa_var = tk.StringVar(value="TODAS")
        combo(2, "Empresa:", self.filtro_empresa_var, ["TODAS"] + organizacao.EMPRESAS, 12)
        self.filtro_status_var = tk.StringVar(value="TODOS")
        combo(4, "Status:", self.filtro_status_var, ["TODOS"] + storage.STATUS_VALIDOS, 12)
        self.ordenacao_var = tk.StringVar(value="Mais recentes")
        combo(6, "Ordenar:", self.ordenacao_var, ["Mais recentes", "Mais antigas"], 13)

        colunas = ("numero", "empresa", "cliente", "codigo", "emissao", "transportadora", "status")
        titulos = {"numero": "Nº da NF", "empresa": "Empresa", "cliente": "Cliente", "codigo": "Código Cliente",
                   "emissao": "Emissão", "transportadora": "Transportadora", "status": "Status"}
        larguras = {"numero": 90, "empresa": 90, "cliente": 230, "codigo": 100, "emissao": 85,
                    "transportadora": 170, "status": 95}

        lista_frame = tk.Frame(self, bg=CORES["fundo_lista"], bd=2, relief="groove")
        lista_frame.pack(fill="both", expand=True, padx=16, pady=6)
        self.tree = ttk.Treeview(lista_frame, columns=colunas, show="headings")
        for c in colunas:
            self.tree.heading(c, text=titulos[c])
            self.tree.column(c, width=larguras[c], anchor="w")
        self.tree.pack(fill="both", expand=True, side="left")
        self.tree.bind("<Double-1>", lambda e: self._abrir_selecionada(self.tree))
        scroll = ttk.Scrollbar(lista_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")

        rodape = tk.Frame(self, bg=fundo)
        rodape.pack(fill="x", padx=16, pady=(6, 16))

        pend = tk.LabelFrame(rodape, text="ATRASADAS (EMITIDA há mais de 3 dias)", bg=fundo, fg=claro)
        pend.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.tree_pendentes = ttk.Treeview(
            pend, columns=("numero", "empresa", "cliente", "dias"), show="headings", height=5)
        for c, t, w in [("numero", "Nº da NF", 85), ("empresa", "Empresa", 85),
                        ("cliente", "Cliente", 210), ("dias", "Dias parada", 85)]:
            self.tree_pendentes.heading(c, text=t)
            self.tree_pendentes.column(c, width=w, anchor="w")
        self.tree_pendentes.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree_pendentes.bind("<Double-1>", lambda e: self._abrir_selecionada(self.tree_pendentes))

        add = tk.LabelFrame(rodape, text="ADICIONAR", bg=fundo, fg=claro)
        add.pack(side="left", fill="y")
        tk.Button(add, text="+ Nova Nota (PDF ou XML)", width=24, height=2, bg=CORES["destaque"],
                  fg=CORES["texto_sobre_destaque"], command=self.adicionar_nota_fiscal).pack(padx=10, pady=(10, 4))
        tk.Button(add, text="+ Importar vários XML", width=24, height=2, bg=CORES["destaque"],
                  fg=CORES["texto_sobre_destaque"], command=self.importar_varios_xml).pack(padx=10, pady=(4, 10))

    def escolher_diretorio(self, primeira_vez=False):
        if primeira_vez:
            messagebox.showinfo(
                "Selecione o diretório",
                "Não foi possível acessar o diretório padrão:\n"
                f"{self.diretorio}\n\n"
                "Selecione a pasta base das notas fiscais (a que contém, ou vai conter, as pastas "
                "DANFE e Canhotos). Depois é possível trocar em 'Configurar diretório'.")
        caminho = filedialog.askdirectory(title="Selecione o diretório base das notas fiscais")
        if caminho:
            self.diretorio = caminho
            config.definir_diretorio_principal(caminho)
            self.atualizar_lista()
            self._checar_pendencias()
        elif primeira_vez:
            messagebox.showwarning("Diretório necessário", "É necessário escolher um diretório para o programa funcionar.")

    def _limpar_busca(self):
        self.busca_var.set("")
        self.atualizar_lista()

    def atualizar_lista(self):
        if not self.diretorio or not os.path.isdir(self.diretorio):
            return
        try:
            self.notas = storage.carregar_notas(self.diretorio)
        except (OSError, ValueError, TimeoutError) as e:
            messagebox.showerror("Erro ao ler notas", str(e))
            return

        termo = self.busca_var.get()
        empresa = self.filtro_empresa_var.get()
        status = self.filtro_status_var.get()

        visiveis = [
            n for n in self.notas
            if (status == "TODOS" or n.get("status") == status)
            and (empresa == "TODAS" or n.get("empresa") == empresa)
            and storage.nota_combina_com_busca(n, termo)
        ]
        visiveis.sort(key=storage.data_para_ordenacao, reverse=self.ordenacao_var.get() != "Mais antigas")

        self.tree.delete(*self.tree.get_children())
        for n in visiveis:
            self.tree.insert("", "end", iid=n["id"], values=(
                n.get("numero_nota", ""), n.get("empresa", ""), n.get("cliente", ""), n.get("codigo_cliente", ""),
                n.get("emissao", ""), n.get("transportadora", ""), n.get("status", "")))

        self.tree_pendentes.delete(*self.tree_pendentes.get_children())
        ids_visiveis = {n["id"] for n in visiveis}
        for n in storage.notas_pendentes(self.notas):
            if n["id"] not in ids_visiveis:
                continue
            self.tree_pendentes.insert("", "end", iid=n["id"], values=(
                n.get("numero_nota", ""), n.get("empresa", ""), n.get("cliente", ""), storage.dias_em_emitida(n)))

    def _checar_pendencias(self):
        pendentes = [n for n in storage.notas_pendentes(self.notas) if not n.get("alerta_dispensado")]
        if pendentes:
            DialogoAlertaPendencias(self, self, pendentes)

    def _abrir_selecionada(self, tree):
        sel = tree.selection()
        if not sel:
            return
        nota = next((n for n in self.notas if n["id"] == sel[0]), None)
        if nota:
            DialogoDetalhesNota(self, self, nota)

    def _diretorio_ok(self):
        if not self.diretorio or not os.path.isdir(self.diretorio):
            messagebox.showwarning("Diretório indisponível",
                                   "O diretório base não está acessível. Verifique a conexão com o servidor "
                                   "ou use 'Configurar diretório'.")
            return False
        return True

    def _processar_arquivo(self, origem, titulo_extra=None):
        """Lê o arquivo, mostra a confirmação e cadastra. True se cadastrou."""
        ext = os.path.splitext(origem)[1].lower()
        if ext == ".xml":
            if not xml_utils.eh_xml_nfe(origem):
                messagebox.showwarning("XML inválido", f"'{os.path.basename(origem)}' não parece ser um XML de NF-e.")
                return False
            campos = xml_utils.extrair_campos_xml(origem)
        elif ext == ".pdf":
            campos = pdf_utils.extrair_campos(origem)
        else:
            messagebox.showwarning("Arquivo inválido", "Selecione um PDF ou XML de NF-e.")
            return False

        dialogo = DialogoNovaNota(self, origem, campos, titulo_extra)
        self.wait_window(dialogo)
        dados = dialogo.resultado
        if not dados:
            return False
        dados["empresa_razao"] = campos.get("empresa_razao", "")

        try:
            duplicada = storage.existe_nota(self.diretorio, dados["numero_nota"], dados["empresa"])
        except (OSError, ValueError, TimeoutError) as e:
            messagebox.showerror("Erro ao ler notas", str(e))
            return False
        if duplicada:
            if not messagebox.askyesno(
                "Nota já cadastrada",
                f"Já existe uma nota {dados['numero_nota']} da empresa {dados['empresa']}.\n"
                "Deseja cadastrar mesmo assim?"):
                return False
        try:
            servico.cadastrar_nota(self.diretorio, origem, dados)
        except (OSError, ValueError, TimeoutError) as e:
            messagebox.showerror("Erro ao salvar a nota", f"Não foi possível salvar os arquivos:\n{e}")
            return False
        return True

    def adicionar_nota_fiscal(self):
        if not self._diretorio_ok():
            return
        origem = filedialog.askopenfilename(title="Selecione a Nota Fiscal (PDF ou XML)", filetypes=FILTRO_NOTA)
        if origem and self._processar_arquivo(origem):
            messagebox.showinfo("Nota adicionada", "A nota fiscal foi cadastrada com status EMITIDA.")
            self.atualizar_lista()

    def importar_varios_xml(self):
        if not self._diretorio_ok():
            return
        origens = filedialog.askopenfilenames(
            title="Selecione um ou mais XML de Notas Fiscais", filetypes=[("XML", "*.xml")])
        if not origens:
            return
        total, cadastradas = len(origens), 0
        for i, origem in enumerate(origens, start=1):
            if self._processar_arquivo(origem, titulo_extra=f"nota {i} de {total}"):
                cadastradas += 1
        self.atualizar_lista()
        messagebox.showinfo("Importação concluída", f"{cadastradas} de {total} nota(s) cadastrada(s).")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()

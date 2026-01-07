import flet as ft
import sqlite3
import os
from datetime import datetime
import locale
from fpdf import FPDF

# --- CONFIGURAÇÃO DE IDIOMA ---
try:
    locale.setlocale(locale.LC_TIME, "pt_BR.utf8")
except:
    locale.setlocale(locale.LC_TIME, "Portuguese_Brazil")

# --- ARQUITETURA DE DADOS: SGBD RELACIONAL ---
def conectar_db():
    caminho_db = os.path.join(os.path.dirname(__file__), "rh_empresa.db")
    return sqlite3.connect(caminho_db, check_same_thread=False)

def init_db():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS funcionarios 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, cpf TEXT, cargo TEXT, 
                       departamento TEXT, salario REAL, data_adm DATE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS atividades_func 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, id_func INTEGER, 
                       data TEXT, hora TEXT, descricao TEXT,
                       FOREIGN KEY(id_func) REFERENCES funcionarios(id))''')
    conn.commit()
    conn.close()

def main(page: ft.Page):
    page.title = "HRMS Engine & Analytics"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 1300
    page.padding = 30
    init_db()

    # --- 1. DECLARAÇÃO DE COMPONENTES DE INTERFACE ---
    # Cadastro
    tf_nome = ft.TextField(label="Nome Completo", expand=True)
    tf_cpf = ft.TextField(label="CPF", width=180)
    tf_cargo = ft.TextField(label="Cargo", expand=True)
    tf_depto = ft.TextField(label="Departamento", expand=True)
    tf_salario = ft.TextField(label="Salário", prefix=ft.Text("R$ "), width=150)
    tf_data_adm = ft.TextField(label="Admissão (DD/MM/AAAA)", width=200)

    # Atividades
    dd_funcionario = ft.Dropdown(label="Selecionar Funcionário", expand=True)
    tf_data_atv = ft.TextField(label="Data", value=datetime.now().strftime("%d/%m/%Y"), width=150)
    tf_hora_atv = ft.TextField(label="Hora", value=datetime.now().strftime("%H:%M"), width=120)
    tf_desc_atv = ft.TextField(label="Descrição", expand=True, multiline=True)
    lista_atividades_hoje = ft.Column(scroll="auto", spacing=10, expand=True)
    
    # Histórico
    tf_filtro_historico = ft.TextField(label="Data de Consulta (DD/MM/AAAA)", expand=True)
    txt_info_dia = ft.Text("", size=18, weight="bold", color="blue200")
    lista_historico = ft.Column(scroll="auto", spacing=10, expand=True)

    # Gerenciamento
    lista_gerenciar_func = ft.Column(scroll="auto", spacing=10, expand=True)

    # --- 2. FUNÇÕES DE APOIO E FEEDBACK ---
    def mostrar_snack(msg):
        page.snack_bar = ft.SnackBar(ft.Text(msg))
        page.snack_bar.open = True
        page.update()

    # --- 3. LÓGICA DE GERENCIAMENTO (FUNCIONÁRIOS) ---
    def deletar_funcionario(id_func):
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM atividades_func WHERE id_func = ?", (id_func,))
        cursor.execute("DELETE FROM funcionarios WHERE id = ?", (id_func,))
        conn.commit()
        conn.close()
        carregar_lista_gerenciamento()
        mostrar_snack("Funcionário e atividades removidos.")

    def abrir_edicao(func_dados):
        # func_dados: (id, nome, cpf, cargo, depto, salario, data_adm)
        edit_id = func_dados[0]
        
        # Campos de edição com os dados atuais
        tf_edit_nome = ft.TextField(label="Nome Completo", value=func_dados[1])
        tf_edit_cpf = ft.TextField(label="CPF", value=func_dados[2])
        tf_edit_cargo = ft.TextField(label="Cargo", value=func_dados[3])
        tf_edit_depto = ft.TextField(label="Departamento", value=func_dados[4])
        tf_edit_salario = ft.TextField(label="Salário", value=str(func_dados[5]), prefix=ft.Text("R$ "))

        def salvar_edicao(e):
            try:
                conn = conectar_db()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE funcionarios 
                    SET nome=?, cpf=?, cargo=?, departamento=?, salario=? 
                    WHERE id=?
                """, (
                    tf_edit_nome.value, 
                    tf_edit_cpf.value, 
                    tf_edit_cargo.value, 
                    tf_edit_depto.value, 
                    float(tf_edit_salario.value or 0), 
                    edit_id
                ))
                conn.commit()
                conn.close()
                
                # Comando para fechar a janela em versões novas e antigas
                if hasattr(page, "close"):
                    page.close(dlg_editar)
                else:
                    dlg_editar.open = False
                
                carregar_lista_gerenciamento()
                mostrar_snack("Cadastro atualizado!")
                page.update()
            except Exception as ex:
                mostrar_snack(f"Erro ao salvar: {ex}")

        # Construção da Janela de Edição (AlertDialog)
        dlg_editar = ft.AlertDialog(
            title=ft.Text("Editar Funcionário"),
            content=ft.Container(
                content=ft.Column([
                    tf_edit_nome,
                    ft.Row([tf_edit_cpf, tf_edit_salario]),
                    ft.Row([tf_edit_cargo, tf_edit_depto]),
                ], tight=True, spacing=10),
                width=500
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: page.close(dlg_editar) if hasattr(page, "close") else setattr(dlg_editar, "open", False) or page.update()),
                ft.ElevatedButton("Salvar", bgcolor="blue", color="white", on_click=salvar_edicao)
            ],
        )

        # COMANDO CRÍTICO: Abre a janela de forma compatível
        if hasattr(page, "open"):
            page.open(dlg_editar) # Padrão Flet Novo
        else:
            page.dialog = dlg_editar
            dlg_editar.open = True # Padrão Flet Antigo
            page.update()

    # --- 1. AJUSTE NO COMPONENTE DE LISTA ---
    # Usar ListView em vez de Column para evitar bugs de renderização e expand
    lista_gerenciar_func = ft.ListView(expand=True, spacing=10, padding=10)

    # --- 2. LÓGICA DE GERENCIAMENTO CORRIGIDA ---
    def carregar_lista_gerenciamento():
        lista_gerenciar_func.controls.clear()
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM funcionarios ORDER BY nome")
        
        for row in cursor.fetchall():
            # Esta linha é vital: cria uma cópia local dos dados para o botão
            dados_do_funcionario = row 

            lista_gerenciar_func.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(row[1], size=16, weight="bold"),
                            ft.Text(f"{row[3]} | {row[4]}", size=12, color="white54"),
                        ], expand=True),
                        
                        # Botão que chama a janela de edição
                        ft.ElevatedButton(
                            "Editar",
                            icon="edit",
                            on_click=lambda _, d=dados_do_funcionario: abrir_edicao(d)
                        ),
                        
                        ft.ElevatedButton(
                            "Excluir",
                            icon="delete",
                            bgcolor="red900",
                            on_click=lambda _, id=dados_do_funcionario[0]: deletar_funcionario(id)
                        ),
                    ]),
                    padding=10, bgcolor="white10", border_radius=10
                )
            )
        conn.close()
        page.update()

    # --- 3. DEFINIÇÃO DA VIEW GERENCIAR ---
    view_gerenciar = ft.Column([
        ft.Text("Gerenciar Funcionários (Edição/Exclusão)", size=24, weight="bold", color="blue200"),
        ft.Divider(color="transparent", height=10),
        # O ListView agora fica dentro de um Container com expand para ocupar a tela
        ft.Container(
            content=lista_gerenciar_func, 
            expand=True, 
            bgcolor="white10", 
            border_radius=15,
            padding=5
        )
    ], visible=False, expand=True)

    # --- 4. LÓGICA DE ATIVIDADES E RELATÓRIOS ---
    def gerar_pdf_diario(e):
        hoje = datetime.now().strftime("%d/%m/%Y")
        conn = conectar_db()
        cursor = conn.cursor()
        query = '''SELECT f.nome, a.hora, a.descricao FROM atividades_func a 
                   JOIN funcionarios f ON a.id_func = f.id WHERE a.data = ? ORDER BY a.hora ASC'''
        cursor.execute(query, (hoje,))
        dados = cursor.fetchall()
        conn.close()
        
        if not dados: return mostrar_snack("Sem atividades para hoje!")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, f"Relatorio Diario - {hoje}", ln=True, align="C")
        pdf.ln(5)
        for r in dados:
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(190, 8, f"[{r[1]}] {r[0]}", fill=True, ln=True, border='T')
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(190, 7, r[2], border='B')
            pdf.ln(2)
        
        nome_arquivo = f"Relatorio_{hoje.replace('/', '_')}.pdf"
        pdf.output(nome_arquivo)
        os.startfile(nome_arquivo)

    def criar_bloco_horizontal(id_atv, nome, hora, desc, data_ref, eh_hist):
        return ft.Container(
            content=ft.Row([
                ft.Column([
                    ft.Text(hora, size=16, weight="bold", color="blue200"),
                    ft.Text(nome, size=11, color="white54", italic=True),
                ], width=140),
                ft.VerticalDivider(width=1, color="white10"),
                ft.Container(content=ft.Text(desc, size=14), expand=True, padding=10),
                ft.TextButton(
                    content=ft.Text("Excluir", color="red400", size=12),
                    on_click=lambda _, i=id_atv: deletar_atividade(i, data_ref, eh_hist)
                ),
            ], vertical_alignment="center"),
            padding=12, bgcolor="white10", border_radius=10, border=ft.border.all(1, "white10")
        )

    def atualizar_view_atividades(lista_alvo, data_filtro, eh_hist=False):
        lista_alvo.controls.clear()
        conn = conectar_db()
        cursor = conn.cursor()
        query = '''SELECT a.id, f.nome, a.hora, a.descricao FROM atividades_func a 
                   JOIN funcionarios f ON a.id_func = f.id WHERE a.data = ? ORDER BY a.hora DESC'''
        cursor.execute(query, (data_filtro,))
        for row in cursor.fetchall():
            lista_alvo.controls.append(criar_bloco_horizontal(row[0], row[1], row[2], row[3], data_filtro, eh_hist))
        conn.close()
        page.update()

    def salvar_atividade(e):
        if not dd_funcionario.value or not tf_desc_atv.value: return
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO atividades_func (id_func, data, hora, descricao) VALUES (?,?,?,?)",
                       (dd_funcionario.value, tf_data_atv.value, tf_hora_atv.value, tf_desc_atv.value))
        conn.commit()
        conn.close()
        tf_desc_atv.value = ""
        atualizar_view_atividades(lista_atividades_hoje, tf_data_atv.value)
        mostrar_snack("Atividade registrada!")

    def deletar_atividade(id_atv, data_ref, eh_hist):
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM atividades_func WHERE id = ?", (id_atv,))
        conn.commit()
        conn.close()
        atualizar_view_atividades(lista_historico if eh_hist else lista_atividades_hoje, data_ref, eh_hist)
        mostrar_snack("Atividade removida.")

    def cadastrar_func(e):
        if not tf_nome.value: return
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO funcionarios (nome, cpf, cargo, departamento, salario, data_adm) VALUES (?,?,?,?,?,?)",
                       (tf_nome.value, tf_cpf.value, tf_cargo.value, tf_depto.value, float(tf_salario.value or 0), tf_data_adm.value))
        conn.commit()
        conn.close()
        for f in [tf_nome, tf_cpf, tf_cargo, tf_depto, tf_salario, tf_data_adm]: f.value = ""
        mostrar_snack("Funcionário cadastrado!")

    def carregar_funcionarios_dd():
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM funcionarios ORDER BY nome")
        dd_funcionario.options = [ft.dropdown.Option(key=str(row[0]), text=row[1]) for row in cursor.fetchall()]
        conn.close()
        page.update()

    # --- 5. DEFINIÇÃO DAS VISÕES (VIEWS) ---
    view_cad = ft.Column([
        ft.Row([tf_nome, tf_cpf]), 
        ft.Row([tf_cargo, tf_depto]),
        ft.Row([tf_salario, tf_data_adm]), 
        ft.ElevatedButton("Salvar Funcionário", icon="save", on_click=cadastrar_func)
    ], visible=True)
    
    view_atv = ft.Column([
        ft.Row([dd_funcionario, tf_data_atv, tf_hora_atv]), 
        ft.Row([tf_desc_atv]),
        ft.Row([
            ft.Button("Registrar Atividade", icon="add", on_click=salvar_atividade),
            ft.ElevatedButton("Imprimir Relatório", icon="print", on_click=gerar_pdf_diario, bgcolor="blue900", color="white"),
        ]),
        ft.Divider(),
        ft.Text("Histórico Recente", size=20, weight="bold"),
        ft.Container(content=lista_atividades_hoje, expand=True, bgcolor="white10", padding=15, border_radius=15)
    ], visible=False, expand=True)

    view_hist = ft.Column([
        ft.Row([tf_filtro_historico, ft.ElevatedButton("Buscar", on_click=lambda _: None)]),
        txt_info_dia,
        ft.Container(content=lista_historico, expand=True, bgcolor="white10", padding=15, border_radius=15)
    ], visible=False, expand=True)

    view_gerenciar = ft.Column([
        ft.Text("Gerenciar Funcionários (Edição/Exclusão)", size=20, weight="bold"),
        ft.Container(content=lista_gerenciar_func, expand=True, bgcolor="white10", padding=15, border_radius=15)
    ], visible=False, expand=True)

    # --- 6. NAVEGAÇÃO E LAYOUT PRINCIPAL ---
    def navegar(e):
        view_cad.visible = (e.control.data == "cad")
        view_atv.visible = (e.control.data == "atv")
        view_hist.visible = (e.control.data == "hist")
        view_gerenciar.visible = (e.control.data == "ger")

        if view_atv.visible: 
            carregar_funcionarios_dd()
            atualizar_view_atividades(lista_atividades_hoje, tf_data_atv.value)
        if view_gerenciar.visible:
            carregar_lista_gerenciamento()
        page.update()

    menu = ft.Row([
        ft.ElevatedButton("Cadastro", on_click=navegar, data="cad"),
        ft.ElevatedButton("Atividades", on_click=navegar, data="atv"),
        ft.ElevatedButton("Histórico", on_click=navegar, data="hist"),
        ft.ElevatedButton("Gerenciar", on_click=navegar, data="ger", bgcolor="blue700", color="white"),
    ])

    page.add(
        ft.Text("RH & Atividades Analytics", size=32, weight="bold", color="blue200"), 
        menu, 
        ft.Divider(), 
        view_cad, 
        view_atv, 
        view_hist, 
        view_gerenciar
    )

if __name__ == "__main__":
    ft.run(main)
import os
import uuid
import secrets
import string
import shutil
import time
import io
import zipfile
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, abort, session, make_response, send_file
from werkzeug.utils import secure_filename

salas_db = {}

app = Flask(__name__)
app.secret_key = 'chave-secreta-sendlock'



# Configração da pasta de upload
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER



# Cria a pasta de upload, caso não exista
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# Tabela de tempos em segundos
TEMPOS_EXPIRACAO = {
    '1d': 24 * 60 * 60,        # 1 Dia (86400s)
    '1s': 7 * 24 * 60 * 60,     # 1 Semana (604800s)
    '1m': 30 * 24 * 60 * 60     # 1 Mês (2592000s)
}


def obter_icone_arquivo(filename):
    ext = filename.lower().split('.')[-1]
    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg']:
        return 'fas fa-file-image'
    elif ext in ['pdf']:
        return 'fas fa-file-pdf'
    elif ext in ['doc', 'docx', 'txt', 'rtf']:
        return 'fas fa-file-alt'
    elif ext in ['xls', 'xlsx', 'csv']:
        return 'fas fa-file-excel'
    elif ext in ['zip', 'rar', 'tar', 'gz']:
        return 'fas fa-file-archive'
    else:
        return 'fas fa-file'

app.jinja_env.globals.update(obter_icone_arquivo = obter_icone_arquivo)


def obter_ou_criar_token_convidado():
    if 'token_convidado' not in session:
        session['token_convidado'] = str(uuid.uuid4())[:8]
    return session['token_convidado']


# Rota principal (Página de início)
@app.route('/')
def inicio():
    return render_template('index.html')



# Rota que cria uma nova sala e redireciona
@app.route('/criar-sala', methods=['POST'])
def criar_sala():
    # Gerar um ID único e curto para a sala
    sala_id = str(uuid.uuid4())[:8]


    # PINs (Admin e CoHost)
    pin_admin = ''.join(secrets.choice(string.digits) for _ in range(6))
    pin_cohost = secrets.token_hex(4)

    pasta_sala = os.path.join(app.config['UPLOAD_FOLDER'], sala_id)
    os.makedirs(pasta_sala, exist_ok=True)

    # Salva os dados
    salas_db[sala_id] = {
        'pin_admin': pin_admin,
        'pin_cohost': pin_cohost,
        'criado_em': time.time(),
        'expiracao_chave': '1d', # Padrão: 1 Dia
        'donos_arquivos': {}
    }

    # Passa os PINs para o usuário ver
    return redirect(url_for('ver_sala', sala_id = sala_id, criador = 'true'))



# Rota da Sala Temporária
@app.route('/sala/<sala_id>')
def ver_sala(sala_id):

    # Se não existir, criar uma sala por segurança
    if sala_id not in salas_db:
        flash('Esta sala expirou ou não existe.', 'erro')
        return redirect(url_for('inicio'))


    sala_atual = salas_db[sala_id]

    # Pega o limite em segundos com base ana chave escolhida (1d, 1s ou 1m)
    chave_expiracao = sala_atual.get('expiracao_chave', '1d')
    limite_segundos = TEMPOS_EXPIRACAO.get(chave_expiracao, 86400)

    # Verifica se a sala expirou
    if time.time() - sala_atual.get('criado_em', time.time()) > limite_segundos:
        pasta_sala = os.path.join(app.config['UPLOAD_FOLDER'], sala_id)

        if os.path.exists(pasta_sala):
            shutil.rmtree(pasta_sala)
        del salas_db[sala_id]

        flash('Esta sala expirou e foi removida por segurança.', 'erro')
        return redirect(url_for('inicio', remover_id = sala_id))


    # Se veio do botão de criar sala, define o papel de admin
    if request.args.get('criador') == 'true':
            session[f'papel_{sala_id}'] = 'admin'
            
            # Redireciona para a mesma sala mas sem o '?criador=true' na URL,
            # limpando a barra de endereços para que o link partilhado fique limpo.
            return redirect(url_for('ver_sala', sala_id=sala_id))

    # Recupera o papel atual do utilizador (padrão: 'convidado')
    papel = session.get(f'papel_{sala_id}', 'convidado')

    # Garante que o visitante tem um token único de convidado
    token_atual = obter_ou_criar_token_convidado()

    # Pega os donos dos arquivos de sala (ou cria um dicionário vazio se não existir)
    sala_atual = salas_db[sala_id]
    donos_arquivos = sala_atual.get('donos_arquivos', {})

    # Listar os arquivos armazenados na pasta e uploads
    arquivos = os.listdir(app.config['UPLOAD_FOLDER'])
    sala_atual = salas_db[sala_id]

    pasta_sala = os.path.join(UPLOAD_FOLDER, sala_id)

    # Lista apenas os arquivos que pertencem à pasta desta sala específica
    arquivos = []
    if os.path.exists(pasta_sala):
        arquivos = os.listdir(pasta_sala)

    return render_template(
        'sala.html', 
        sala_id = sala_id,
        papel = papel,
        arquivos = arquivos, 
        pin_admin = sala_atual['pin_admin'],
        pin_cohost = sala_atual['pin_cohost'],
        expiracao_atual = chave_expiracao,
        donos_arquivos = donos_arquivos
    )



# Rota via PIN (Admin e CoHost)
@app.route('/sala/<sala_id>/login', methods=['POST'])
def login_sala(sala_id):
    pin_digitado = request.form.get('pin')
    sala = salas_db.get(sala_id)

    if not sala:
        flash('Sala não encontrada!', 'erro')
        return redirect(url_for('inicio'))

    if pin_digitado == sala['pin_admin']:
        session[f'papel_{sala_id}'] = 'admin'
        flash('Modo Administrador ativado com sucesso!', 'sucesso')
    
    elif pin_digitado == sala['pin_cohost']:
        session[f'papel_{sala_id}'] = 'cohost'
        flash('Modo Coanfitrião ativado com sucesso!', 'sucesso')

    else:
        flash('PIN incorreto!', 'erro')

    return redirect(url_for('ver_sala', sala_id = sala_id))



# Rota de upload do arquivo
@app.route('/sala/<sala_id>/upload', methods = ['POST'])

def upload_arquivo(sala_id):
    if 'arquivo' not in request.files:
        flash('Nenhum arquivo enviado.')
        return redirect(url_for('ver_sala', sala_id = sala_id))

    arquivos = request.files.getlist('arquivo')

    if not arquivos or arquivos[0].filename == '':
        flash('Nenhum arquivo selecionado.')
        return redirect(url_for('ver_sala', sala_id = sala_id))

    # Cria um caminho para a pasta específica
    pasta_sala = os.path.join(app.config['UPLOAD_FOLDER'], sala_id)
    os.makedirs(pasta_sala, exist_ok=True)

    token_atual = obter_ou_criar_token_convidado()
    sala = salas_db[sala_id]

    
    if 'donos_arquivos' not in sala:
            sala['donos_arquivos'] = {}


    for arquivo in arquivos:
        if arquivo:
            # Sanitiza (Detetiza kk) o nome do arquivo para segurança
            nome_seguro = secure_filename(arquivo.filename)

            # Salva o arquivo DENTRO da pasta específica da sala
            caminho_salvar = os.path.join(pasta_sala, nome_seguro)
            arquivo.save(caminho_salvar)

            sala['donos_arquivos'][nome_seguro] = token_atual

    flash('Arquivo enviado com sucesso!', 'sucesso')
    return redirect(url_for('ver_sala', sala_id = sala_id))
    


# Downloads
@app.route('/sala/<sala_id>/download/<filename>')
def download_arquivo(sala_id, filename):
    
    # Subpasta específica da pasta da sala
    pasta_sala = os.path.join(app.config['UPLOAD_FOLDER'], sala_id)

    if os.path.exists(os.path.join(pasta_sala, filename)):
        return send_from_directory(pasta_sala, filename, as_attachment=True)
    else:
        #abort(404, description='Arquivo não encontrado!')
        flash('Arquivo não encontrado!', 'erro')
        return redirect(url_for('ver_sala', sala_id = sala_id))



# Excluir arquivos
@app.route('/sala/<sala_id>/deletar/<filename>', methods=['POST'])
def deletar_arquivo(sala_id, filename):

    # Verifica o papel atual: apenas Admin e CoHost podem apagar
    papel = session.get(f'papel_{sala_id}', 'convidado')
    token_atual = obter_ou_criar_token_convidado()

    sala = salas_db.get(sala_id, {})
    donos = sala.get('donos_arquivos', {})
    dono_arquivo = donos.get(filename)

    if papel not in ['admin', 'cohost'] and token_atual != dono_arquivo:
        flash('Acesso negado: apenas Admiistradores e Coanfitriões podem excluir arquivos.', 'erro')
        return redirect(url_for('ver_sala', sala_id = sala_id))

    # Aponta para a subpasta específica da sala
    pasta_sala = os.path.join(app.config['UPLOAD_FOLDER'], sala_id)
    caminho_arquivo = os.path.join(pasta_sala, filename)

    if os.path.exists(caminho_arquivo):
        os.remove(caminho_arquivo)

        if filename in donos:
            del donos[filename]

        flash('Arquivo excluído com sucesso!', 'sucesso')

    return redirect(url_for('ver_sala', sala_id = sala_id))


# Rota para sair da sessão (Voltar como Convidado)
@app.route('/sala/<sala_id>/sair')
def sair_sessao(sala_id):

    # Remover o papel da sessão, se existir
    session.pop(f'papel_{sala_id}', None)
    flash('Sessão encerrada.', 'sucesso')
    return redirect(url_for('ver_sala', sala_id = sala_id))

# Rota para apagar a sala e a sua pasta física
@app.route('/sala/<sala_id>/excluir-pasta', methods=['POST'])
def excluir_pasta_sala(sala_id):
    pasta_sala = os.path.join(app.config['UPLOAD_FOLDER'], sala_id)

    # Se a pasta física existir, é apagada junto com todos os arquivos
    if os.path.exists(pasta_sala):
        shutil.rmtree(pasta_sala)

    # Remove também do dicionário em memória, se existir
    if sala_id in salas_db:
        del salas_db[sala_id]

    return '', 204 # Retorna sucesso vazio para o JavaScript

# Rota de expiração
@app.route('/sala/<sala_id>/definir-expiracao', methods=['POST'])
def definir_expiracao(sala_id):
    papel = session.get(f'papel_{sala_id}', 'convidado')

    # Apenas o Admin pode alterar
    if papel != 'admin':
        flash('Apenas administradores podem alterar a expiração.', 'erro')
        return redirect(url_for('ver_sala', sala_id = sala_id))

    nova_opcao = request.form.get('duracao')
    if nova_opcao in TEMPOS_EXPIRACAO:
        if sala_id in salas_db:
            salas_db[sala_id]['expiracao_chave'] = nova_opcao
            flash(f'Tempo de expiração atualizado', 'sucesso')

    return redirect(url_for('ver_sala', sala_id = sala_id))



@app.route('/sala/<sala_id>/download-todos')
def download_todos_arquivos(sala_id):
    pasta_sala = os.path.join(app.config['UPLOAD_FOLDER'], sala_id)

    if not os.path.exists(pasta_sala) or not os.listdir(pasta_sala):
        flash('Nenhum arquivo para baixar.', 'erro')
        return redirect(url_for('ver_sala', sala_id = sala_id))

    # Cria o arquivo zip diretamente na memória RAM
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(pasta_sala):
            for file in files:
                caminho_completo = os.path.join(root, file)
                zf.write(caminho_completo, arcname=file)

    memory_file.seek(0)

    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'SendLock_Sala_{sala_id}.zip'
    )



# Deletar TODOS os arquivos
@app.route('/sala/<sala_id>/deletar-todos', methods=['POST'])
def deletar_todos_arquivos(sala_id):
    papel = session.get(f'papel_{sala_id}', 'convidado')

    if papel not in ['admin', 'cohost']:
        flash('Acesso negado.', 'erro')
        return redirect(url_for('ver_sala', sala_id = sala_id))

    pasta_sala = os.path.join(app.config['UPLOAD_FOLDER'], sala_id)

    if os.path.exists(pasta_sala):
        # Esvazia os arquivos mantendo a pasta da sala
        for filename in os.listdir(pasta_sala):
            caminho_arquivo = os.path.join(pasta_sala, filename)
            if os.path.isfile(caminho_arquivo):
                os.remove(caminho_arquivo)

        if sala_id in salas_db:
            salas_db[sala_id]['donos_arquivos'] = {}

        flash('Todos os arquivos foram excluídos com sucesso!', 'sucesso')

    return redirect(url_for('ver_sala', sala_id = sala_id))


if __name__ == '__main__':
    # Roda a aplicação em modo de desenvolvedor na porta 5000
    app.run(debug = True, port = 5000)
import os
import uuid
import secrets
import string
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, abort, session, make_response
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


    # Salva os dados
    salas_db[sala_id] = {
        'arquivos': [],
        'pin_admin': pin_admin,
        'pin_cohost': pin_cohost
    }

    # Guarda quem é o admin
    session[f'papel_{sala_id}'] = 'admin'

    print(f"[CRIAR] Sala criada: {sala_id} | Papel na sessão definido como {session.get(f'papel_{sala_id}')}")

    # Passa os PINs para o usuário ver
    return redirect(url_for('ver_sala', sala_id = sala_id))



# Rota da Sala Temporária
@app.route('/sala/<sala_id>')
def ver_sala(sala_id):

    print(f"[VER_SALA] Acedendo à sala: {sala_id}")
    print(f"[VER_SALA] Salas ativas no DB: {list(salas_db.keys())}")
    print(f"[VER_SALA] Papel atual na sessão: {session.get(f'papel_{sala_id}')}")

    # Se não existir, criar uma sala por segurança
    if sala_id not in salas_db:
        flash('Esta sala expirou ou não existe.', 'erro')
        return redirect(url_for('inicio'))

    # Recupera o papel atual do utilizador (padrão: 'convidado')
    papel = session.get(f'papel_{sala_id}', 'convidado')


    # Se a URL vier com ?admin=true, guarda na sessão
    if request.args.get('admin') == 'true':
        papel = 'admin'
        session[f'papel_{sala_id}'] = 'admin'


    # Listar os arquivos armazenados na pasta e uploads
    arquivos = os.listdir(app.config['UPLOAD_FOLDER'])

    sala_atual = salas_db[sala_id]
    return render_template(
        'sala.html', 
        sala_id = sala_id,
        papel = papel,
        arquivos = arquivos, 
        pin_admin = sala_atual['pin_admin'],
        pin_cohost = sala_atual['pin_cohost'] 
        
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
        return redirect(url_for('ver_sala', sala_id = sala_id, admin = 'true'))

    arquivos = request.files.getlist('arquivo')

    if not arquivos or arquivos[0].filename == '':
        flash('Nenhum arquivo selecionado.')
        return redirect(url_for('ver_sala', sala_id = sala_id, admin = 'true'))

    for arquivo in arquivos:
        if arquivo:
            # Sanitiza (Detetiza kk) o nome do arquivo para segurança
            nome_seguro = secure_filename(arquivo.filename)
            caminho_salvar = os.path.join(app.config['UPLOAD_FOLDER'], nome_seguro)
            arquivo.save(caminho_salvar)

    flash('Arquivo enviado com sucesso!', 'sucesso')
    return redirect(url_for('ver_sala', sala_id = sala_id, admin = 'true'))
    


# Downloads
@app.route('/sala/<sala_id>/download/<filename>')
def download_arquivo(sala_id, filename):
    # Caminho específico da pasta da sala
    caminho_sala = app.config['UPLOAD_FOLDER']

    if os.path.exists(os.path.join(caminho_sala, filename)):
        # Pega o token enviado, se houver
#        token = request.args.get('token')

        # Executa o envido
        response = make_response(send_from_directory(caminho_sala, filename, as_attachment=True))

        # Se tiver tokens, define o cookie para saber que terminou
#        if token:
#            response.set_cookie(f'fileDownloadToken_{token}', 'true', max_age=10)
            
        return send_from_directory(caminho_sala, filename, as_attachment=True)
    else:
        abort(404, description='Arquivo não encontrado!')



# Excluir arquivos
@app.route('/sala/<sala_id>/deletar/<filename>', methods=['POST'])
def deletar_arquivo(sala_id, filename):

    # Verifica o papel atual: apenas Admin e CoHost podem apagar
    papel = session.get(f'papel_{sala_id}', 'convidado')

    if papel not in ['admin', 'cohost']:
        flash('Acesso negado: apenas Admiistradores e Coanfitriões podem excluir arquivos.', 'erro')
        return redirect(url_for('ver_sala', sala_id = sala_id))

    caminho_pasta = app.config['UPLOAD_FOLDER']
    caminho_arquivo = os.path.join(caminho_pasta, filename)

    if os.path.exists(caminho_arquivo):
        os.remove(caminho_arquivo)
        flash('Arquivo excluído com sucesso!', 'sucesso')

    return redirect(url_for('ver_sala', sala_id = sala_id))



if __name__ == '__main__':
    # Roda a aplicação em modo de desenvolvedor na porta 5000
    app.run(debug = True, port = 5000)
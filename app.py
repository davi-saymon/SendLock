import os
import uuid
from flask import Flask, render_template, redirect, url_for, request, flash, send_from_directory, abort, session
from werkzeug.utils import secure_filename



app = Flask(__name__)
app.secret_key = 'chave-secreta-sendlock'



# Configração da pasta de upload
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER



# Cria a pasta de upload, caso não exista
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)



# Rota principal (Página de início)
@app.route('/')
def inicio():
    return render_template('index.html')



# Rota que cria uma nova sala e redireciona
@app.route('/criar-sala', methods=['POST'])
def criar_sala():
    # Gerar um ID único e curto para a sala
    sala_id = str(uuid.uuid4())[:8]

    # Guarda quem é o admin
    session[f'admin_{sala_id}'] = True

    # Redireciona o usuário para a página da sala recém-criada
    return redirect(url_for('ver_sala', sala_id = sala_id))



# Rota da Sala Temporária
@app.route('/sala/<sala_id>')
def ver_sala(sala_id):
    # Se a URL vier com ?admin=true, guarda na sessão
    if request.args.get('admin') == 'true':
        session[f'admin_{sala_id}'] = True

    # Verifica o estado de admin da sessão
    is_admin = session.get(f'admin_{sala_id}', False)

    # Listar os arquivos armazenados na pasta e uploads
    arquivos = os.listdir(app.config['UPLOAD_FOLDER'])

    return render_template('sala.html', sala_id = sala_id, is_admin = is_admin, arquivos = arquivos)



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

    flash('Arquivo enviado com sucesso!')
    return redirect(url_for('ver_sala', sala_id = sala_id, admin = 'true'))
    


# Downloads
@app.route('/sala/<sala_id>/download/<filename>')
def download_arquivo(sala_id, filename):
    # Caminho específico da pasta da sala
    caminho_sala = app.config['UPLOAD_FOLDER']

    try:
        return send_from_directory(caminho_sala, filename, as_attachment=True)
    except FileNotFoundError:
        abort(404, description='Arquivo não encontrado!')



# Excluir arquivos
@app.route('/sala/<sala_id>/deletar/<filename>', methods=['POST'])
def deletar_arquivo(sala_id, filename):
    # Verifica se é o Admin
    if not session.get(f'admin_{sala_id}', False):
        return redirect(url_for('ver_sala', sala_id = sala_id))

    caminho_pasta = app.config['UPLOAD_FOLDER']
    caminho_arquivo = os.path.join(caminho_pasta, filename)

    if os.path.exists(caminho_arquivo):
        os.remove(caminho_arquivo)

    return redirect(url_for('ver_sala', sala_id = sala_id))



if __name__ == '__main__':
    # Roda a aplicação em modo de desenvolvedor na porta 5000
    app.run(debug = True, port = 5000)
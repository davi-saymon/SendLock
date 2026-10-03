import uuid
from flask import Flask, render_template, redirect, url_for, request

app = Flask(__name__)

# Rota principal (Página de início)
@app.route('/')
def inicio():
    return render_template('index.html')

# Rota que cria uma nova sala e redireciona
@app.route('/criar-sala', methods=['POST'])
def criar_sala():
    # Gerar um ID único e curto para a sala
    sala_id = str(uuid.uuid4())[:8]

    # Redireciona o usuário para a página da sala recém-criada
    return redirect(url_for('ver_sala', sala_id = sala_id, admin = 'true'))

# Rota da Sala Temporária
@app.route('/sala/<sala_id>')
def ver_sala(sala_id):
    # Por enquanto, renderiza a mesma página mostrando o ID da sala
    is_admin = request.args.get('admin') == 'true'
    return render_template('sala.html', sala_id = sala_id, is_admin = is_admin)


if __name__ == '__main__':
    # Roda a aplicação em modo de desenvolvedor na porta 5000
    app.run(debug = True, port = 5000)
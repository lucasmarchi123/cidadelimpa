/*
 * Sugestões de ruas no formulário de denúncia.
 *
 * Este é o único JavaScript do site. Ele faz duas coisas:
 * 1. Mantém o formulário travado até a pessoa escolher o município.
 * 2. Ao escolher o município, busca as ruas dele e sugere nomes enquanto a
 *    pessoa digita, ignorando maiúsculas, acentos e abreviações (R., Av.).
 *
 * Se o script não carregar, o formulário funciona normalmente: a pessoa digita
 * a rua, e o servidor corrige o nome quando ele existe na lista oficial.
 */
(function () {
  'use strict';

  var form = document.querySelector('[data-form-denuncia]');
  if (!form) return;

  var municipio = form.querySelector('#id_municipio');
  var campo = form.querySelector('#id_logradouro');
  var lista = form.querySelector('#lista-ruas');
  var ajuda = form.querySelector('#ajuda-ruas');
  var aviso = form.querySelector('[data-aviso-municipio]');
  var urlModelo = form.getAttribute('data-url-ruas');   // termina em "/0/"
  if (!municipio || !campo || !lista || !ajuda || !urlModelo) return;

  var MAX_SUGESTOES = 8;
  var ABREVIACOES = { r: 'rua', av: 'avenida', tv: 'travessa', trav: 'travessa' };

  var ruas = [];          // [{ nome: 'Rua São José', busca: 'rua sao jose' }]
  var cidadeAtual = '';
  var memoria = {};       // ruas já baixadas, por município
  var sugestoes = [];
  var ativa = -1;

  /* "R. São  José" vira "rua sao jose": sem acento, minúsculo, sem abreviação */
  function normalizar(texto) {
    var palavras = (texto || '')
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[.,]/g, ' ')
      .split(/\s+/).filter(Boolean);
    if (palavras.length && ABREVIACOES[palavras[0]]) palavras[0] = ABREVIACOES[palavras[0]];
    return palavras.join(' ');
  }

  /* ---------- trava do formulário até escolher o município ---------- */

  var outrosCampos = Array.prototype.filter.call(
    form.querySelectorAll('input, select, textarea, button'),
    function (el) { return el !== municipio && el.type !== 'hidden'; }
  );

  function travar(travado) {
    outrosCampos.forEach(function (el) { el.disabled = travado; });
    form.classList.toggle('nova__form--aguardando', travado);
    if (aviso) aviso.hidden = !travado;
  }

  /* ---------- acessibilidade: o campo vira uma "caixa de combinação" ---------- */

  campo.setAttribute('autocomplete', 'off');
  campo.setAttribute('role', 'combobox');
  campo.setAttribute('aria-autocomplete', 'list');
  campo.setAttribute('aria-controls', 'lista-ruas');
  campo.setAttribute('aria-expanded', 'false');
  campo.setAttribute('aria-describedby', 'ajuda-ruas');

  /* ---------- buscar as ruas do município escolhido ---------- */

  function nomeDaCidade() {
    var opcao = municipio.options[municipio.selectedIndex];
    return opcao ? opcao.text : '';
  }

  function avisar(texto, alerta) {
    ajuda.textContent = texto;
    ajuda.classList.toggle('campo__ajuda--alerta', !!alerta);
  }

  function anunciarLista() {
    if (ruas.length) {
      avisar('Comece a digitar para ver as ruas de ' + cidadeAtual + '.');
    } else {
      avisar('Ainda não temos a lista de ruas de ' + cidadeAtual + '. Digite o nome normalmente.');
    }
  }

  function carregarRuas() {
    var id = municipio.value;
    fechar();
    ruas = [];
    if (!id) {
      travar(true);
      avisar('');
      return;
    }
    travar(false);
    cidadeAtual = nomeDaCidade();

    if (memoria[id]) {
      ruas = memoria[id];
      anunciarLista();
      return;
    }

    avisar('Carregando as ruas de ' + cidadeAtual + '...');
    var url = urlModelo.replace(/0\/$/, id + '/');
    fetch(url, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (resposta) {
        if (!resposta.ok) throw new Error('HTTP ' + resposta.status);
        return resposta.json();
      })
      .then(function (dados) {
        memoria[id] = dados.ruas.map(function (nome) {
          return { nome: nome, busca: normalizar(nome) };
        });
        if (municipio.value === id) {     // a pessoa pode ter trocado de cidade nesse meio-tempo
          ruas = memoria[id];
          anunciarLista();
        }
      })
      .catch(function () {
        avisar('Não foi possível carregar a lista de ruas. Digite o nome normalmente.');
      });
  }

  /* ---------- filtrar e mostrar sugestões ---------- */

  function filtrar(texto) {
    var consulta = normalizar(texto);
    if (consulta.length < 2) return [];
    var noInicio = [], inicioDePalavra = [], noMeio = [];
    for (var i = 0; i < ruas.length; i++) {
      var posicao = ruas[i].busca.indexOf(consulta);
      if (posicao === -1) continue;
      if (posicao === 0) noInicio.push(ruas[i]);
      else if (ruas[i].busca.charAt(posicao - 1) === ' ') inicioDePalavra.push(ruas[i]);
      else noMeio.push(ruas[i]);
    }
    return noInicio.concat(inicioDePalavra, noMeio).slice(0, MAX_SUGESTOES);
  }

  function fechar() {
    lista.hidden = true;
    lista.innerHTML = '';
    campo.setAttribute('aria-expanded', 'false');
    campo.removeAttribute('aria-activedescendant');
    sugestoes = [];
    ativa = -1;
  }

  function mostrar(itens) {
    fechar();
    if (!itens.length) return;
    sugestoes = itens;
    itens.forEach(function (rua, i) {
      var item = document.createElement('li');
      item.id = 'rua-sugestao-' + i;
      item.setAttribute('role', 'option');
      item.setAttribute('aria-selected', 'false');
      item.textContent = rua.nome;   // textContent: o nome nunca é interpretado como HTML
      item.addEventListener('mousedown', function (evento) {
        evento.preventDefault();     // não deixa o campo perder o foco antes da escolha
        escolher(i);
      });
      lista.appendChild(item);
    });
    lista.hidden = false;
    campo.setAttribute('aria-expanded', 'true');
  }

  function destacar(indice) {
    var itens = lista.children;
    if (!itens.length) return;
    ativa = (indice + itens.length) % itens.length;
    for (var i = 0; i < itens.length; i++) {
      itens[i].setAttribute('aria-selected', i === ativa ? 'true' : 'false');
    }
    campo.setAttribute('aria-activedescendant', itens[ativa].id);
    itens[ativa].scrollIntoView({ block: 'nearest' });
  }

  function escolher(i) {
    campo.value = sugestoes[i].nome;
    fechar();
    avisar('Rua encontrada na lista de ' + cidadeAtual + '.');
  }

  /* Ao sair do campo: corrige a grafia ou avisa que a rua não está na lista */
  function conferir() {
    var digitado = campo.value.trim();
    if (!digitado || !ruas.length) return;
    var alvo = normalizar(digitado);
    for (var i = 0; i < ruas.length; i++) {
      if (ruas[i].busca === alvo) {
        campo.value = ruas[i].nome;
        avisar('Rua encontrada na lista de ' + cidadeAtual + '.');
        return;
      }
    }
    avisar('Não encontramos essa rua na lista de ' + cidadeAtual +
           '. Confira o nome. Se estiver certo, pode continuar.', true);
  }

  /* ---------- eventos ---------- */

  municipio.addEventListener('change', carregarRuas);

  campo.addEventListener('input', function () {
    if (ruas.length) anunciarLista();
    mostrar(filtrar(campo.value));
  });

  campo.addEventListener('keydown', function (evento) {
    var aberta = !lista.hidden;
    if (evento.key === 'ArrowDown') {
      if (!aberta) mostrar(filtrar(campo.value));
      destacar(ativa + 1);
      evento.preventDefault();
    } else if (evento.key === 'ArrowUp' && aberta) {
      destacar(ativa - 1);
      evento.preventDefault();
    } else if (evento.key === 'Enter' && aberta && ativa >= 0) {
      escolher(ativa);
      evento.preventDefault();        // escolhe a rua em vez de enviar o formulário
    } else if (evento.key === 'Escape' && aberta) {
      fechar();
    }
  });

  campo.addEventListener('blur', function () {
    fechar();
    conferir();
  });

  carregarRuas();   // estado inicial: trava, ou carrega a cidade que já veio escolhida
})();

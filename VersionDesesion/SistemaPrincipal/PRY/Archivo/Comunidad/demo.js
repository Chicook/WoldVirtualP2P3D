// ===== Idiomas =====
const I18N = {
  es:{title:'FLUJO E2E · DAO 3D',f:['Recepción','Alta','Isla Embossed','P2P + LucIA'],st:['LucIA: modo demo (Ollama sin conectar)','Nodos P2P: 3 simulados'],lt:'LucIA · Avatar AI',lp:'Hola, soy LucIA. Estoy en la Isla Embossed 3D. ¡Bienvenido al mundo P2P!',btn:'Copiar ruta del lanzador',on:'Sonido',off:'Silencio'},
  en:{title:'E2E FLOW · 3D DAO',f:['Reception','Sign-up','Embossed Island','P2P + LucIA'],st:['LucIA: demo mode (Ollama not connected)','P2P nodes: 3 simulated'],lt:'LucIA · AI Avatar',lp:'Hi, I am LucIA. I live on the Embossed 3D Island. Welcome to the P2P world!',btn:'Copy launcher path',on:'Sound',off:'Muted'},
  fr:{title:'FLUX E2E · DAO 3D',f:['Accueil','Inscription','Île Embossed','P2P + LucIA'],st:['LucIA : mode démo (Ollama non connecté)','Nœuds P2P : 3 simulés'],lt:'LucIA · Avatar IA',lp:'Bonjour, je suis LucIA. Je suis sur l’île Embossed 3D. Bienvenue dans le monde P2P !',btn:'Copier le chemin du lanceur',on:'Son',off:'Muet'},
  ha:{title:'TSARIN E2E · DAO 3D',f:['Karɓa','Rajista','Tsibirin Embossed','P2P + LucIA'],st:['LucIA: yanayin gwaji (ba a haɗa Ollama ba)','Nodes na P2P: 3 na kwaikwayo'],lt:'LucIA · Avatar ta AI',lp:'Sannu, ni ce LucIA. Ina Tsibirin Embossed na 3D. Maraba da zuwa duniyar P2P!',btn:'Kwafi hanyar mai ƙaddamarwa',on:'Sauti',off:'Shiru'},
  pt:{title:'FLUXO E2E · DAO 3D',f:['Recepção','Cadastro','Ilha Embossed','P2P + LucIA'],st:['LucIA: modo demo (Ollama não conectado)','Nós P2P: 3 simulados'],lt:'LucIA · Avatar de IA',lp:'Olá, sou a LucIA. Estou na Ilha Embossed 3D. Bem-vindo ao mundo P2P!',btn:'Copiar caminho do lançador',on:'Som',off:'Mudo'},
  ar:{title:'تدفق E2E · DAO ثلاثي الأبعاد',f:['الاستقبال','التسجيل','جزيرة Embossed','P2P + LucIA'],st:['LucIA: وضع تجريبي (Ollama غير متصل)','عقد P2P: 3 محاكاة'],lt:'LucIA · أفاتار ذكي',lp:'مرحبًا، أنا LucIA. أنا في جزيرة Embossed ثلاثية الأبعاد. أهلًا بك في عالم P2P!',btn:'نسخ مسار المشغّل',on:'صوت',off:'صامت'}
};
let cur = I18N.es, soundOn = false;
const sndBtn = document.getElementById('snd');

function applyLang(l) {
  if (!I18N[l]) l = 'es';
  const d = cur = I18N[l];
  document.documentElement.lang = l;
  document.documentElement.dir = l === 'ar' ? 'rtl' : 'ltr';
  document.querySelector('.panel h3').textContent = d.title;
  document.querySelectorAll('.flow span').forEach((s, i) => s.textContent = d.f[i]);
  const sd = document.querySelectorAll('.stats div');
  d.st.forEach((s, i) => sd[i].innerHTML = '<span class="dot"></span>' + s);
  document.getElementById('lt').textContent = d.lt + ' ▾';
  document.querySelector('#lucia-chat p').textContent = d.lp;
  document.getElementById('launch').textContent = d.btn;
  sndBtn.textContent = soundOn ? '🔊 ' + d.on : '🔇 ' + d.off;
  document.getElementById('lang').value = l;
  try { localStorage.setItem('wv-lang', l); } catch (e) {}
}
document.getElementById('lang').addEventListener('change', e => applyLang(e.target.value));

// ===== Sonido ambiente suave (Web Audio, sin archivos) =====
let ac, master, bellTimer, vol = 0.5;
function buildAudio() {
  ac = new (window.AudioContext || window.webkitAudioContext)();
  master = ac.createGain(); master.gain.value = 0; master.connect(ac.destination);
  const lp = ac.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 700; lp.connect(master);
  const lf = ac.createOscillator(); lf.frequency.value = 0.05;
  const lfg = ac.createGain(); lfg.gain.value = 300;
  lf.connect(lfg); lfg.connect(lp.frequency); lf.start();
  // Acorde lento que "respira"
  [110, 164.81, 220, 277.18].forEach((f, i) => {
    const o = ac.createOscillator(); o.type = i % 2 ? 'sine' : 'triangle';
    o.frequency.value = f; o.detune.value = (i - 1.5) * 4;
    const g = ac.createGain(); g.gain.value = 0.08;
    const l = ac.createOscillator(); l.frequency.value = 0.05 + i * 0.03;
    const lg = ac.createGain(); lg.gain.value = 0.05;
    l.connect(lg); lg.connect(g.gain);
    o.connect(g); g.connect(lp); o.start(); l.start();
  });
  // Olas del mar
  const buf = ac.createBuffer(1, ac.sampleRate * 4, ac.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  const n = ac.createBufferSource(); n.buffer = buf; n.loop = true;
  const nf = ac.createBiquadFilter(); nf.type = 'lowpass'; nf.frequency.value = 420;
  const ng = ac.createGain(); ng.gain.value = 0.05;
  const wl = ac.createOscillator(); wl.frequency.value = 0.1;
  const wg = ac.createGain(); wg.gain.value = 0.04;
  wl.connect(wg); wg.connect(ng.gain);
  n.connect(nf); nf.connect(ng); ng.connect(master); n.start(); wl.start();
}
function bell() {
  const notes = [440, 493.88, 554.37, 659.25, 739.99];
  const o = ac.createOscillator(); o.type = 'sine';
  o.frequency.value = notes[Math.floor(Math.random() * notes.length)];
  const g = ac.createGain(), t0 = ac.currentTime;
  g.gain.setValueAtTime(0, t0);
  g.gain.linearRampToValueAtTime(0.06, t0 + 0.05);
  g.gain.exponentialRampToValueAtTime(0.0001, t0 + 4);
  o.connect(g); g.connect(master); o.start(t0); o.stop(t0 + 4.2);
}
sndBtn.addEventListener('click', async () => {
  soundOn = !soundOn;
  try {
    if (soundOn) {
      if (!ac) buildAudio();
      await ac.resume();
      master.gain.setTargetAtTime(vol, ac.currentTime, 2);
      bellTimer = setInterval(bell, 6500);
    } else if (ac) {
      clearInterval(bellTimer);
      master.gain.setTargetAtTime(0, ac.currentTime, 1.2);
      setTimeout(() => { if (!soundOn) ac.suspend(); }, 4000);
    }
  } catch (e) { soundOn = false; }
  applyLang(document.getElementById('lang').value);
});
document.getElementById('vol').addEventListener('input', e => {
  vol = +e.target.value;
  if (ac && soundOn) master.gain.setTargetAtTime(vol, ac.currentTime, 0.3);
});

let saved = null;
try { saved = localStorage.getItem('wv-lang'); } catch (e) {}
applyLang(saved || (navigator.language || 'es').slice(0, 2));

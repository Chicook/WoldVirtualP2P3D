// Comprobacion: ¿puede este modelo usar tool-calling a traves del endpoint
// OpenAI-compatible de Ollama con el prompt real de OpenCode (~6k tokens)?
// Uso: node comprobar_ollama.mjs [modelo]   (por defecto wvp-opencode)
const BASE = 'http://127.0.0.1:11434';
const MODEL = process.argv[2] || 'wvp-opencode';

// System prompt de relleno del tamano del que usa OpenCode (20k caracteres).
const filler = 'OpenCode es un agente de terminal. '.repeat(600);
const TOOLS = ['bash', 'edit', 'glob', 'grep', 'read', 'skill', 'task', 'todowrite', 'webfetch', 'write'].map((n) => ({
  type: 'function',
  function: {
    name: n,
    description: `Herramienta ${n} del agente de codigo.`,
    parameters: { type: 'object', properties: { path: { type: 'string' }, content: { type: 'string' } }, required: [] },
  },
}));

const r = await fetch(`${BASE}/v1/chat/completions`, {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    model: MODEL,
    stream: false,
    max_tokens: 200,
    messages: [
      { role: 'system', content: filler },
      { role: 'user', content: 'Crea el archivo PRUEBA_PERMISO.txt con el contenido: edicion local OK' },
    ],
    tools: TOOLS,
  }),
});

const j = await r.json();
const m = j.choices?.[0]?.message;
const promptTokens = j.usage?.prompt_tokens ?? 0;
const toolCalls = m?.tool_calls?.map((t) => t.function.name) ?? null;
const needed = TOOLS.length + Math.ceil(filler.length / 4);

console.log(JSON.stringify({
  modelo: MODEL,
  prompt_tokens: promptTokens,
  tools_recibidas: promptTokens > 5000 ? 'si (no hay truncado)' : 'NO (truncado por num_ctx)',
  tool_calls: toolCalls,
  veredicto: toolCalls ? 'EDITABLE' : 'NO EDITA',
  texto: (m?.content || '').slice(0, 80).replace(/\n/g, ' '),
}, null, 1));

if (!toolCalls) {
  console.log(`\nEl contexto efectiva es pequena: se procesaron ${promptTokens} tokens cuando hacen falta ~${needed}.`);
  console.log(`Sube num_ctx (Modelfile + ollama create) o usa OLLAMA_CONTEXT_LENGTH.`);
  process.exit(1);
}

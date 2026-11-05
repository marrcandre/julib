<script setup lang="ts">
import { ref, onMounted } from "vue";
import QRCode from "qrcode";
import Button from "primevue/button";
import { useToast } from "primevue/usetoast";
const toast = useToast();
const copied = ref(""),
  qr = ref(""),
  pix = "marcoandre@gmail.com";
const tlv = (id: string, value: string) =>
  id + String(value.length).padStart(2, "0") + value;
function pixPayload() {
  let payload =
    tlv("00", "01") +
    tlv("26", tlv("00", "BR.GOV.BCB.PIX") + tlv("01", pix)) +
    tlv("52", "0000") +
    tlv("53", "986") +
    tlv("58", "BR") +
    tlv("59", "MARCO ANDRE MENDES") +
    tlv("60", "JOINVILLE") +
    tlv("62", tlv("05", "***")) +
    "6304";
  let crc = 0xffff;
  for (const c of payload) {
    crc ^= c.charCodeAt(0) << 8;
    for (let i = 0; i < 8; i++)
      crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
  }
  return payload + crc.toString(16).toUpperCase().padStart(4, "0");
}
async function copy() {
  try {
    await navigator.clipboard.writeText(pix);
    copied.value = "";
    toast.removeAllGroups();
    toast.add({
      severity: "success",
      summary: "Chave PIX copiada.",
      life: 3500,
    });
  } catch {
    copied.value = "Não foi possível copiar. Selecione a chave acima.";
  }
}
onMounted(async () => {
  qr.value = await QRCode.toDataURL(pixPayload(), {
    width: 180,
    margin: 2,
    color: { dark: "#053227", light: "#ffffff" },
  });
  if (location.hash) document.querySelector(location.hash)?.scrollIntoView();
});
</script>
<template>
  <article class="readable">
    <div class="eyebrow">SOBRE O PROJETO</div>
    <h1>Uma biblioteca cheia de histórias.</h1>
    <p>
      Julib é uma aplicação gratuita e de código aberto para organizar
      bibliotecas pessoais: livros, exemplares, locais e empréstimos, juntos em
      um só lugar.
    </p>
    <section id="homenagem">
      <h2>Uma homenagem à Juliana Mendes</h2>
      <p>
        O nome <b>Julib</b> une <b>Ju</b>, de Juliana, e <b>lib</b>, referência
        a biblioteca. Uma homenagem de Marco André Mendes à sua esposa, com quem
        compartilha o acervo e o amor pelos livros.
      </p>
    </section>
    <h2>Como funciona</h2>
    <p>
      Busque livros por título, autor ou ISBN, leia o código de barras pela
      câmera ou importe uma seleção do Goodreads. Organize os exemplares por
      local, estante e prateleira, use tags e acompanhe empréstimos e
      devoluções.
    </p>
    <h2>Privacidade</h2>
    <p>
      O gerenciamento exige uma conta Google autorizada. Localizações, contatos
      e histórico de empréstimos são privados. Um link de consulta opcional
      mostra somente dados dos livros, tags e disponibilidade; esse link pode
      ser desativado ou renovado pelos gestores.
    </p>
    <h2>Tecnologias</h2>
    <div class="tag-list">
      <span
        v-for="tech in [
          'Django',
          'Django Ninja',
          'Python',
          'Vue',
          'TypeScript',
          'PrimeVue',
          'PostgreSQL',
          'Supabase',
          'Cloudinary',
          'Vercel',
        ]"
        :key="tech"
        class="tag-pill"
        >{{ tech }}</span
      >
    </div>
    <h2>Autor</h2>
    <p>Desenvolvido e mantido por <b>Marco André Mendes</b>.</p>
    <div class="actions">
      <a href="https://github.com/marrcandre" target="_blank" rel="noopener"
        >GitHub</a
      ><a
        href="https://www.linkedin.com/in/marrcandre/"
        target="_blank"
        rel="noopener"
        >LinkedIn</a
      ><a href="mailto:marcoandre@gmail.com">Contato</a>
    </div>
    <h2>Código aberto</h2>
    <p>
      Distribuído sob a licença MIT. Sugestões, relatos de problemas e
      contribuições são bem-vindos.
    </p>
    <a href="https://github.com/marrcandre/julib" target="_blank" rel="noopener"
      >Código fonte e contribuições →</a
    >
    <h2>Outros projetos</h2>
    <div class="panel">
      <h3>Dons Espirituais</h3>
      <p>Uma ferramenta de reflexão sobre dons espirituais.</p>
      <a
        href="https://dons-espirituais.vercel.app"
        target="_blank"
        rel="noopener"
        >Conhecer Dons →</a
      >
      <h3>Cinco Ministérios</h3>
      <p>
        Uma ferramenta de reflexão sobre os cinco ministérios de Efésios 4:11.
      </p>
      <a
        href="https://cinco-ministerios.vercel.app"
        target="_blank"
        rel="noopener"
        >Conhecer Cinco Ministérios →</a
      >
    </div>
    <section
      id="apoie"
      class="panel"
      style="margin-top: 36px; border-color: #daaa60"
    >
      <h2 style="margin-top: 0">Apoie este projeto</h2>
      <p>
        Se o Julib é útil para você, uma contribuição voluntária ajuda a manter
        e desenvolver o projeto. O uso da aplicação continua gratuito.
      </p>
      <img
        v-if="qr"
        :src="qr"
        alt="QR Code PIX para apoiar o projeto"
        width="180"
        height="180"
      />
      <p>
        <code>{{ pix }}</code>
      </p>
      <Button
        label="Copiar chave PIX"
        icon="pi pi-copy"
        class="primary"
        @click="copy"
      />
      <p v-if="copied" class="error" role="alert">{{ copied }}</p>
    </section>
  </article>
</template>

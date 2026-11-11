# Atribuicao de terceiros

Este projeto usa modelos e bibliotecas de terceiros. As atribuicoes abaixo
sao exigidas pelas respectivas licencas.

---

## speaker-diarization-community-1

- Fonte: https://huggingface.co/pyannote/speaker-diarization-community-1
- Autores: Herve Bredin e a equipe pyannoteAI / pyannote.audio
- Licenca: Creative Commons Attribution 4.0 International (CC-BY-4.0)
  https://creativecommons.org/licenses/by/4.0/
- Modificacoes: nenhuma. Os pesos sao usados sem retreino, fine-tuning,
  quantizacao ou conversao.

O pipeline inclui pesos PLDA atribuidos ao BUT Speech@FIT; a integracao do VBx
no pyannote.audio e de Jiangyu Han e Petr Palka.

Citacao:

    @inproceedings{Plaquet23,
      author={Alexis Plaquet and Herve Bredin},
      title={{Powerset multi-class cross entropy loss for neural speaker
              diarization}},
      year=2023, booktitle={Proc. INTERSPEECH 2023},
    }

---

## wespeaker-voxceleb-resnet34-LM

- Fonte: https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM
- Licenca: CC-BY-4.0
- Modificacoes: nenhuma.
- Modelo de embedding de falante do toolkit WeSpeaker, treinado em VoxCeleb.

NAO USE o espelho publicado sob cc-by-nc-4.0 (NonCommercial): inviabiliza uso
comercial. Confira a licenca declarada de qualquer copia antes de baixar.

Citacao:

    @inproceedings{Wang2023,
      title={Wespeaker: A research and production oriented speaker embedding
             learning toolkit},
      author={Wang, Hongji and Liang, Chengdong and Wang, Shuai and Chen,
              Zhengyang and Zhang, Binbin and Xiang, Xu and Deng, Yanlei and
              Qian, Yanmin},
      booktitle={ICASSP 2023}, organization={IEEE}
    }

---

## pyannote.audio

- Fonte: https://github.com/pyannote/pyannote-audio
- Licenca: MIT

---

## Whisper

- Fonte: https://github.com/openai/whisper
- Autor: OpenAI
- Licenca: MIT
- Usado via mlx-whisper (MLX, Apple) ou faster-whisper (CTranslate2).
  Verifique a licenca da porta especifica que voce distribuir.

---

## Literata

- Fonte: https://github.com/googlefonts/literata
- Autores: Ricardo Marcin / TypeTogether, contribuidores Google Fonts
- Licenca: SIL Open Font License 1.1
- Modificacoes: nenhuma. Arquivos `.woff2` (pesos 400 e 600) empacotados em
  `frontend/src/estilos/fontes/` (SKILL.md de identidade visual, ADR 0005).

---

## IBM Plex Mono

- Fonte: https://github.com/IBM/plex
- Autor: IBM
- Licenca: SIL Open Font License 1.1 (Reserved Font Name "Plex")
- Modificacoes: nenhuma. Arquivo `.woff2` (peso 400) empacotado em
  `frontend/src/estilos/fontes/`. Texto da licenca em
  `frontend/public/licencas/OFL-ibm-plex.txt`. A IBM Plex Sans saiu do app
  com a marca Trama (ADR 0023).

---

## Figtree

- Fonte: https://github.com/erikdkennedy/figtree
- Autor: Erik Kennedy (The Figtree Project Authors)
- Licenca: SIL Open Font License 1.1 (sem Reserved Font Name)
- Modificacoes: subset latin (U+0000-00FF e pontuacao), como distribuido
  pelo Fontsource (`@fontsource/figtree` 5.3.0). Arquivos `.woff2` (pesos
  400 e 600) empacotados em `frontend/src/estilos/fontes/`. Texto da
  licenca em `frontend/public/licencas/OFL-figtree.txt`. Interface do app
  (marca Trama, ADR 0023).

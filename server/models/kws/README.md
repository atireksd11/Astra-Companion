# Hey Astra keyword model

English int8 Zipformer keyword spotter from sherpa-onnx.

Source: https://github.com/k2-fsa/sherpa-onnx/releases/download/kws-models/sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01.tar.bz2

Files kept from that pack (int8 only):

- `encoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx`
- `decoder-epoch-12-avg-2-chunk-16-left-64.int8.onnx`
- `joiner-epoch-12-avg-2-chunk-16-left-64.int8.onnx`
- `tokens.txt`
- `bpe.model`

The only keyword is `hey astra` (`keywords_raw.txt` is the line `HEY ASTRA`).
Build `keywords.txt` with:

```
sherpa-onnx-cli text2token --tokens tokens.txt --tokens-type bpe --bpe-model bpe.model keywords_raw.txt keywords.txt
```

That CLI ships with `sherpa-onnx` and also needs `sentencepiece` and `pypinyin`.

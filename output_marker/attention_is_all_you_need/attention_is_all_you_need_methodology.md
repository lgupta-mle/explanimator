constraint of sequential computation, however, remains.

are used in conjunction with a recurrent network.

To the best of our knowledge, however, the Transformer is the first transduction model relying entirely on self-attention to compute representations of its input and output without using sequencealigned RNNs or convolution. In the following sections, we will describe the Transformer, motivate self-attention and discuss its advantages over models such as [\[17,](#page-10-12) [18\]](#page-10-8) and [\[9\]](#page-10-9).

Recurrent neural networks, long short-term memory [\[13\]](#page-10-0) and gated recurrent [\[7\]](#page-10-1) neural networks in particular, have been firmly established as state of the art approaches in sequence modeling and transduction problems such as language modeling and machine translation [\[35,](#page-11-0) [2,](#page-9-0) [5\]](#page-10-2). Numerous efforts have since continued to push the boundaries of recurrent language models and encoder-decoder

Recurrent models typically factor computation along the symbol positions of the input and output sequences. Aligning the positions to steps in computation time, they generate a sequence of hidden states ht, as a function of the previous hidden state ht−<sup>1</sup> and the input for position t. This inherently sequential nature precludes parallelization within training examples, which becomes critical at longer sequence lengths, as memory constraints limit batching across examples. Recent work has achieved significant improvements in computational efficiency through factorization tricks [\[21\]](#page-10-5) and conditional computation [\[32\]](#page-11-2), while also improving model performance in case of the latter. The fundamental

Attention mechanisms have become an integral part of compelling sequence modeling and transduction models in various tasks, allowing modeling of dependencies without regard to their distance in the input or output sequences [\[2,](#page-9-0) [19\]](#page-10-6). In all but a few cases [\[27\]](#page-11-3), however, such attention mechanisms

In this work we propose the Transformer, a model architecture eschewing recurrence and instead relying entirely on an attention mechanism to draw global dependencies between input and output. The Transformer allows for significantly more parallelization and can reach a new state of the art in

The goal of reducing sequential computation also forms the foundation of the Extended Neural GPU [\[16\]](#page-10-7), ByteNet [\[18\]](#page-10-8) and ConvS2S [\[9\]](#page-10-9), all of which use convolutional neural networks as basic building block, computing hidden representations in parallel for all input and output positions. In these models, the number of operations required to relate signals from two arbitrary input or output positions grows in the distance between positions, linearly for ConvS2S and logarithmically for ByteNet. This makes it more difficult to learn dependencies between distant positions [\[12\]](#page-10-10). In the Transformer this is reduced to a constant number of operations, albeit at the cost of reduced effective resolution due to averaging attention-weighted positions, an effect we counteract with Multi-Head Attention as

Self-attention, sometimes called intra-attention is an attention mechanism relating different positions of a single sequence in order to compute a representation of the sequence. Self-attention has been used successfully in a variety of tasks including reading comprehension, abstractive summarization,

End-to-end memory networks are based on a recurrent attention mechanism instead of sequencealigned recurrence and have been shown to perform well on simple-language question answering and

textual entailment and learning task-independent sentence representations [\[4,](#page-9-1) [27,](#page-11-3) [28,](#page-11-4) [22\]](#page-10-11).

translation quality after being trained for as little as twelve hours on eight P100 GPUs.

Most competitive neural sequence transduction models have an encoder-decoder structure [\[5,](#page-10-2) [2,](#page-9-0) [35\]](#page-11-0). Here, the encoder maps an input sequence of symbol representations (x1, ..., xn) to a sequence of continuous representations z = (z1, ..., zn). Given z, the decoder then generates an output sequence (y1, ..., ym) of symbols one element at a time. At each step the model is auto-regressive [\[10\]](#page-10-13), consuming the previously generated symbols as additional input when generating the next.

layers, produce outputs of dimension dmodel = 512. Decoder: The decoder is also composed of a stack of N = 6 identical layers. In addition to the two sub-layers in each encoder layer, the decoder inserts a third sub-layer, which performs multi-head attention over the output of the encoder stack. Similar to the encoder, we employ residual connections around each of the sub-layers, followed by layer normalization. We also modify the self-attention sub-layer in the decoder stack to prevent positions from attending to subsequent positions. This masking, combined with fact that the output embeddings are offset by one position, ensures that the

<span id="page-2-1"></span>The Transformer follows this overall architecture using stacked self-attention and point-wise, fully connected layers for both the encoder and decoder, shown in the left and right halves of Figure [1,](#page-2-1)

Encoder: The encoder is composed of a stack of N = 6 identical layers. Each layer has two sub-layers. The first is a multi-head self-attention mechanism, and the second is a simple, positionwise fully connected feed-forward network. We employ a residual connection [\[11\]](#page-10-14) around each of the two sub-layers, followed by layer normalization [\[1\]](#page-9-2). That is, the output of each sub-layer is LayerNorm(x + Sublayer(x)), where Sublayer(x) is the function implemented by the sub-layer itself. To facilitate these residual connections, all sub-layers in the model, as well as the embedding

respectively.

<span id="page-2-0"></span>3.2 Attention
<sup>∗</sup>Equal contribution. Listing order is random. Jakob proposed replacing RNNs with self-attention and started the effort to evaluate this idea. Ashish, with Illia, designed and implemented the first Transformer models and has been crucially involved in every aspect of this work. Noam proposed scaled dot-product attention, multi-head attention and the parameter-free position representation and became the other person involved in nearly every detail. Niki designed, implemented, tuned and evaluated countless model variants in our original codebase and tensor2tensor. Llion also experimented with novel model variants, was responsible for our initial codebase, and efficient inference and visualizations. Lukasz and Aidan spent countless long days designing various parts of and implementing tensor2tensor, replacing our earlier codebase, greatly improving results and massively accelerating our research.

Provided proper attribution is provided, Google hereby grants permission to reproduce the tables and figures in this paper solely for use in journalistic or scholarly works.

Attention Is All You Need

Niki Parmar<sup>∗</sup> Google Research nikip@google.com

Jakob Uszkoreit<sup>∗</sup> Google Research usz@google.com

Łukasz Kaiser<sup>∗</sup> Google Brain lukaszkaiser@google.com

Noam Shazeer<sup>∗</sup> Google Brain noam@google.com

Aidan N. Gomez∗ † University of Toronto aidan@cs.toronto.edu

Illia Polosukhin∗ ‡ illia.polosukhin@gmail.com

Abstract

The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely. Experiments on two machine translation tasks show these models to be superior in quality while being more parallelizable and requiring significantly less time to train. Our model achieves 28.4 BLEU on the WMT 2014 Englishto-German translation task, improving over the existing best results, including ensembles, by over 2 BLEU. On the WMT 2014 English-to-French translation task, our model establishes a new single-model state-of-the-art BLEU score of 41.8 after training for 3.5 days on eight GPUs, a small fraction of the training costs of the best models from the literature. We show that the Transformer generalizes well to other tasks by applying it successfully to English constituency parsing both with

Ashish Vaswani<sup>∗</sup> Google Brain avaswani@google.com

> Llion Jones<sup>∗</sup> Google Research llion@google.com

> > large and limited training data.

†Work performed while at Google Brain. ‡Work performed while at Google Research.

# 1 Introduction

architectures [\[38,](#page-11-1) [24,](#page-10-3) [15\]](#page-10-4).

2 Background

described in section [3.2.](#page-2-0)

language modeling tasks [\[34\]](#page-11-5).

3 Model Architecture

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

![](_page_2_Figure_0.jpeg)

layers, produce outputs of dimension dmodel = 512. Decoder: The decoder is also composed of a stack of N = 6 identical layers. In addition to the two sub-layers in each encoder layer, the decoder inserts a third sub-layer, which performs multi-head attention over the output of the encoder stack. Similar to the encoder, we employ residual connections around each of the sub-layers, followed by layer normalization. We also modify the self-attention sub-layer in the decoder stack to prevent positions from attending to subsequent positions. This masking, combined with fact that the output embeddings are offset by one position, ensures that the

<span id="page-2-1"></span>The Transformer follows this overall architecture using stacked self-attention and point-wise, fully connected layers for both the encoder and decoder, shown in the left and right halves of Figure [1,](#page-2-1)

Encoder: The encoder is composed of a stack of N = 6 identical layers. Each layer has two sub-layers. The first is a multi-head self-attention mechanism, and the second is a simple, positionwise fully connected feed-forward network. We employ a residual connection [\[11\]](#page-10-14) around each of the two sub-layers, followed by layer normalization [\[1\]](#page-9-2). That is, the output of each sub-layer is LayerNorm(x + Sublayer(x)), where Sublayer(x) is the function implemented by the sub-layer itself. To facilitate these residual connections, all sub-layers in the model, as well as the embedding

respectively.

<span id="page-2-0"></span>3.2 Attention

3.1 Encoder and Decoder Stacks

An attention function can be described as mapping a query and a set of key-value pairs to an output, where the query, keys, values, and output are all vectors. The output is computed as a weighted sum

3

predictions for position i can depend only on the known outputs at positions less than i.

#### Scaled Dot-Product Attention

Scale

MatMul

attention layers running in parallel.

query with the corresponding key.

the matrix of outputs as:

matrix multiplication code.

<span id="page-3-2"></span>3.2.2 Multi-Head Attention

values.

3.2.1 Scaled Dot-Product Attention

MatMul

Multi-Head Attention

Linear

Concat

Scaled Dot-Product Attention

Linear

Q

(1)

Linea

<span id="page-3-0"></span>Figure 2: (left) Scaled Dot-Product Attention. (right) Multi-Head Attention consists of several

of the values, where the weight assigned to each value is computed by a compatibility function of the

We call our particular attention "Scaled Dot-Product Attention" (Figure 2). The input consists of queries and keys of dimension  $d_k$ , and values of dimension  $d_v$ . We compute the dot products of the query with all keys, divide each by  $\sqrt{d_k}$ , and apply a softmax function to obtain the weights on the

In practice, we compute the attention function on a set of queries simultaneously, packed together into a matrix Q. The keys and values are also packed together into matrices K and V. We compute

 $Attention(Q, K, V) = softmax(\frac{QK^T}{\sqrt{d_k}})V$ 

The two most commonly used attention functions are additive attention [2], and dot-product (multiplicative) attention. Dot-product attention is identical to our algorithm, except for the scaling factor of  $\frac{1}{\sqrt{d_k}}$ . Additive attention computes the compatibility function using a feed-forward network with a single hidden layer. While the two are similar in theoretical complexity, dot-product attention is much faster and more space-efficient in practice, since it can be implemented using highly optimized

While for small values of  $d_k$  the two mechanisms perform similarly, additive attention outperforms dot product attention without scaling for larger values of  $d_k$  [3]. We suspect that for large values of  $d_k$ , the dot products grow large in magnitude, pushing the softmax function into regions where it has

extremely small gradients <sup>4</sup>. To counteract this effect, we scale the dot products by  $\frac{1}{\sqrt{d_*}}$ 

<span id="page-3-1"></span><sup>4</sup>To illustrate why the dot products get large, assume that the components of q and k are independent random variables with mean 0 and variance 1. Then their dot product,  $q \cdot k = \sum_{i=1}^{d_k} q_i k_i$ , has mean 0 and variance  $d_k$ .

4

Instead of performing a single attention function with  $d_{\text{model}}$ -dimensional keys, values and queries, we found it beneficial to linearly project the queries, keys and values h times with different, learned linear projections to  $d_k$ ,  $d_k$  and  $d_v$  dimensions, respectively. On each of these projected versions of queries, keys and values we then perform the attention function in parallel, yielding  $d_v$ -dimensional

output values. These are concatenated and once again projected, resulting in the final values, as depicted in Figure [2.](#page-3-0)

Multi-head attention allows the model to jointly attend to information from different representation

MultiHead(Q, K, V ) = Concat(head1, ..., headh)W<sup>O</sup> where head<sup>i</sup> = Attention(QW<sup>Q</sup>

subspaces at different positions. With a single attention head, averaging inhibits this.

Where the projections are parameter matrices W Q <sup>i</sup> <sup>∈</sup> <sup>R</sup> <sup>d</sup>model×d<sup>k</sup> , W <sup>K</sup> <sup>i</sup> ∈ R <sup>d</sup>model×d<sup>k</sup> , W<sup>V</sup> <sup>i</sup> ∈ R dmodel×d<sup>v</sup> and W<sup>O</sup> ∈ R hdv×dmodel .

In this work we employ h = 8 parallel attention layers, or heads. For each of these we use d<sup>k</sup> = d<sup>v</sup> = dmodel/h = 64. Due to the reduced dimension of each head, the total computational cost

• In "encoder-decoder attention" layers, the queries come from the previous decoder layer, and the memory keys and values come from the output of the encoder. This allows every position in the decoder to attend over all positions in the input sequence. This mimics the typical encoder-decoder attention mechanisms in sequence-to-sequence models such as

• The encoder contains self-attention layers. In a self-attention layer all of the keys, values and queries come from the same place, in this case, the output of the previous layer in the encoder. Each position in the encoder can attend to all positions in the previous layer of the

• Similarly, self-attention layers in the decoder allow each position in the decoder to attend to all positions in the decoder up to and including that position. We need to prevent leftward information flow in the decoder to preserve the auto-regressive property. We implement this inside of scaled dot-product attention by masking out (setting to −∞) all values in the input

In addition to attention sub-layers, each of the layers in our encoder and decoder contains a fully connected feed-forward network, which is applied to each position separately and identically. This

While the linear transformations are the same across different positions, they use different parameters from layer to layer. Another way of describing this is as two convolutions with kernel size 1. The dimensionality of input and output is dmodel = 512, and the inner-layer has dimensionality

FFN(x) = max(0, xW<sup>1</sup> + b1)W<sup>2</sup> + b<sup>2</sup> (2)

of the softmax which correspond to illegal connections. See Figure [2.](#page-3-0)

consists of two linear transformations with a ReLU activation in between.

i

, KW <sup>K</sup> i

, V W<sup>V</sup> i )

The Transformer uses multi-head attention in three different ways:

3.2.3 Applications of Attention in our Model

3.3 Position-wise Feed-Forward Networks

[\[38,](#page-11-1) [2,](#page-9-0) [9\]](#page-10-9).

encoder.

df f = 2048.

3.4 Embeddings and Softmax

is similar to that of single-head attention with full dimensionality.

Similarly to other sequence transduction models, we use learned embeddings to convert the input tokens and output tokens to vectors of dimension dmodel. We also use the usual learned linear transformation and softmax function to convert the decoder output to predicted next-token probabilities. In our model, we share the same weight matrix between the two embedding layers and the pre-softmax linear transformation, similar to [\[30\]](#page-11-6). In the embedding layers, we multiply those weights by <sup>√</sup> dmodel.

5

<span id="page-5-0"></span>Table 1: Maximum path lengths, per-layer complexity and minimum number of sequential operations for different layer types. n is the sequence length, d is the representation dimension, k is the kernel size of convolutions and r the size of the neighborhood in restricted self-attention.

Since our model contains no recurrence and no convolution, in order for the model to make use of the order of the sequence, we must inject some information about the relative or absolute position of the tokens in the sequence. To this end, we add "positional encodings" to the input embeddings at the bottoms of the encoder and decoder stacks. The positional encodings have the same dimension  $d_{\rm model}$  as the embeddings, so that the two can be summed. There are many choices of positional encodings,

 $PE_{(pos,2i)} = sin(pos/10000^{2i/d_{model}})$  $PE_{(pos,2i+1)} = cos(pos/10000^{2i/d_{model}})$ 

where pos is the position and i is the dimension. That is, each dimension of the positional encoding corresponds to a sinusoid. The wavelengths form a geometric progression from  $2\pi$  to  $10000 \cdot 2\pi$ . We chose this function because we hypothesized it would allow the model to easily learn to attend by relative positions, since for any fixed offset k,  $PE_{pos+k}$  can be represented as a linear function of

We also experimented with using learned positional embeddings [9] instead, and found that the two versions produced nearly identical results (see Table 3 row (E)). We chose the sinusoidal version because it may allow the model to extrapolate to sequence lengths longer than the ones encountered

In this section we compare various aspects of self-attention layers to the recurrent and convolutional layers commonly used for mapping one variable-length sequence of symbol representations  $(x_1,...,x_n)$  to another sequence of equal length  $(z_1,...,z_n)$ , with  $x_i,z_i \in \mathbb{R}^d$ , such as a hidden layer in a typical sequence transduction encoder or decoder. Motivating our use of self-attention we

Sequential

**Operations** 

O(1)

O(n)

O(1)

O(1)

Maximum Path Length

O(1)

O(n)

 $O(log_k(n))$ 

O(n/r)

Complexity per Layer

 $O(n^2 \cdot d)$ 

 $O(n \cdot d^2)$ 

 $O(k \cdot n \cdot d^2)$ 

 $O(r \cdot n \cdot d)$ 

In this work, we use sine and cosine functions of different frequencies:

# 3.5 Positional Encoding

learned and fixed [9].

 $PE_{pos}$ .

during training.

Why Self-Attention

consider three desiderata.

different layer types.

Self-Attention (restricted)

Layer Type

Recurrent

Self-Attention

Convolutional

be parallelized, as measured by the minimum number of sequential operations required. The third is the path length between long-range dependencies in the network. Learning long-range dependencies is a key challenge in many sequence transduction tasks. One key factor affecting the ability to learn such dependencies is the length of the paths forward and backward signals have to traverse in the network. The shorter these paths between any combination of positions in the input and output sequences, the easier it is to learn long-range dependencies [12]. Hence we also compare the maximum path length between any two input and output positions in networks composed of the

As noted in Table 1, a self-attention layer connects all positions with a constant number of sequentially executed operations, whereas a recurrent layer requires O(n) sequential operations. In terms of computational complexity, self-attention layers are faster than recurrent layers when the sequence

6

One is the total computational complexity per layer. Another is the amount of computation that can

length n is smaller than the representation dimensionality d, which is most often the case with sentence representations used by state-of-the-art models in machine translations, such as word-piece [\[38\]](#page-11-1) and byte-pair [\[31\]](#page-11-7) representations. To improve computational performance for tasks involving very long sequences, self-attention could be restricted to considering only a neighborhood of size r in the input sequence centered around the respective output position. This would increase the maximum path length to O(n/r). We plan to investigate this approach further in future work.

A single convolutional layer with kernel width k < n does not connect all pairs of input and output positions. Doing so requires a stack of O(n/k) convolutional layers in the case of contiguous kernels, or O(logk(n)) in the case of dilated convolutions [\[18\]](#page-10-8), increasing the length of the longest paths between any two positions in the network. Convolutional layers are generally more expensive than recurrent layers, by a factor of k. Separable convolutions [\[6\]](#page-10-15), however, decrease the complexity

convolution is equal to the combination of a self-attention layer and a point-wise feed-forward layer,

As side benefit, self-attention could yield more interpretable models. We inspect attention distributions from our models and present and discuss examples in the appendix. Not only do individual attention heads clearly learn to perform different tasks, many appear to exhibit behavior related to the syntactic

). Even with k = n, however, the complexity of a separable

. We varied the learning

) (3)

2

This section describes the training regime for our models.

considerably, to O(k · n · d + n · d

the approach we take in our model.

and semantic structure of the sentences.

5.1 Training Data and Batching

5 Training

We trained on the standard WMT 2014 English-German dataset consisting of about 4.5 million sentence pairs. Sentences were encoded using byte-pair encoding [\[3\]](#page-9-3), which has a shared sourcetarget vocabulary of about 37000 tokens. For English-French, we used the significantly larger WMT 2014 English-French dataset consisting of 36M sentences and split tokens into a 32000 word-piece vocabulary [\[38\]](#page-11-1). Sentence pairs were batched together by approximate sequence length. Each training batch contained a set of sentence pairs containing approximately 25000 source tokens and 25000 target tokens.

We trained our models on one machine with 8 NVIDIA P100 GPUs. For our base models using the hyperparameters described throughout the paper, each training step took about 0.4 seconds. We trained the base models for a total of 100,000 steps or 12 hours. For our big models,(described on the bottom line of table [3\)](#page-8-0), step time was 1.0 seconds. The big models were trained for 300,000 steps

## 5.2 Hardware and Schedule

lrate = d

(3.5 days).

5.3 Optimizer

<span id="page-6-0"></span>5.4 Regularization

This corresponds to increasing the learning rate linearly for the first warmup\_steps training steps, and decreasing it thereafter proportionally to the inverse square root of the step number. We used warmup\_steps = 4000.

7

, step\_num · warmup\_steps<sup>−</sup>1.<sup>5</sup>

We employ three types of regularization during training:

rate over the course of training, according to the formula:

−0.5

We used the Adam optimizer [\[20\]](#page-10-16) with β<sup>1</sup> = 0.9, β<sup>2</sup> = 0.98 and ϵ = 10<sup>−</sup><sup>9</sup>

model · min(step\_num<sup>−</sup>0.<sup>5</sup>

| Table 2: The Transformer achieves better BLEU scores than previous state-of-the-art models on the |
|---------------------------------------------------------------------------------------------------|
| English-to-German and English-to-French newstest2014 tests at a fraction of the training cost.    |

<span id="page-7-0"></span>

| Model                           | BL    | EU    | Training Cost (FLOPs) |                     |  |
|---------------------------------|-------|-------|-----------------------|---------------------|--|
| Wiodei                          | EN-DE | EN-FR | EN-DE                 | EN-FR               |  |
| ByteNet [18]                    | 23.75 |       |                       |                     |  |
| Deep-Att + PosUnk [39]          |       | 39.2  |                       | $1.0 \cdot 10^{20}$ |  |
| GNMT + RL [38]                  | 24.6  | 39.92 | $2.3 \cdot 10^{19}$   | $1.4 \cdot 10^{20}$ |  |
| ConvS2S [9]                     | 25.16 | 40.46 | $9.6 \cdot 10^{18}$   | $1.5 \cdot 10^{20}$ |  |
| MoE [32]                        | 26.03 | 40.56 | $2.0\cdot 10^{19}$    | $1.2\cdot 10^{20}$  |  |
| Deep-Att + PosUnk Ensemble [39] |       | 40.4  |                       | $8.0 \cdot 10^{20}$ |  |
| GNMT + RL Ensemble [38]         | 26.30 | 41.16 | $1.8 \cdot 10^{20}$   | $1.1 \cdot 10^{21}$ |  |
| ConvS2S Ensemble [9]            | 26.36 | 41.29 | $7.7\cdot10^{19}$     | $1.2 \cdot 10^{21}$ |  |
| Transformer (base model)        | 27.3  | 38.1  |                       | $10^{18}$           |  |
| Transformer (big)               | 28.4  | 41.8  | $2.3 \cdot 10^{19}$   |                     |  |

**Residual Dropout** We apply dropout [33] to the output of each sub-layer, before it is added to the sub-layer input and normalized. In addition, we apply dropout to the sums of the embeddings and the positional encodings in both the encoder and decoder stacks. For the base model, we use a rate of

**Label Smoothing** During training, we employed label smoothing of value  $\epsilon_{ls} = 0.1$  [36]. This hurts perplexity, as the model learns to be more unsure, but improves accuracy and BLEU score.

On the WMT 2014 English-to-German translation task, the big transformer model (Transformer (big) in Table 2) outperforms the best previously reported models (including ensembles) by more than 2.0 BLEU, establishing a new state-of-the-art BLEU score of 28.4. The configuration of this model is listed in the bottom line of Table 3. Training took 3.5 days on 8 P100 GPUs. Even our base model surpasses all previously published models and ensembles, at a fraction of the training cost of any of

On the WMT 2014 English-to-French translation task, our big model achieves a BLEU score of 41.0, outperforming all of the previously published single models, at less than 1/4 the training cost of the previous state-of-the-art model. The Transformer (big) model trained for English-to-French used

For the base models, we used a single model obtained by averaging the last 5 checkpoints, which were written at 10-minute intervals. For the big models, we averaged the last 20 checkpoints. We used beam search with a beam size of 4 and length penalty  $\alpha = 0.6$  [38]. These hyperparameters were chosen after experimentation on the development set. We set the maximum output length during

Table 2 summarizes our results and compares our translation quality and training costs to other model architectures from the literature. We estimate the number of floating point operations used to train a model by multiplying the training time, the number of GPUs used, and an estimate of the sustained

inference to input length + 50, but terminate early when possible [38].

single-precision floating-point capacity of each GPU <sup>5</sup>.

 $P_{drop} = 0.1.$ 

Results

6.1 Machine Translation

the competitive models.

**6.2** Model Variations

dropout rate  $P_{drop} = 0.1$ , instead of 0.3.

<span id="page-7-1"></span>To evaluate the importance of different components of the Transformer, we varied our base model in different ways, measuring the change in performance on English-to-German translation on the

5We used values of 2.8, 3.7, 6.0 and 9.5 TFLOPS for K80, K40, M40 and P100, respectively.

8

<span id="page-8-0"></span>Table 3: Variations on the Transformer architecture. Unlisted values are identical to those of the base model. All metrics are on the English-to-German translation development set, newstest2013. Listed perplexities are per-wordpiece, according to our byte-pair encoding, and should not be compared to per-word perplexities.

|      | N                                         | dmodel | dff  | h  | dk  | dv   | Pdrop | ϵls | train<br>steps | PPL<br>(dev) | BLEU<br>(dev) | params<br>×106 |
|------|-------------------------------------------|--------|------|----|-----|------|-------|-----|----------------|--------------|---------------|----------------|
| base | 6                                         | 512    | 2048 | 8  | 64  | 64   | 0.1   | 0.1 | 100K           | 4.92         | 25.8          | 65             |
| (A)  |                                           |        |      | 1  | 512 | 512  |       |     |                | 5.29         | 24.9          |                |
|      |                                           |        |      | 4  | 128 | 128  |       |     |                | 5.00         | 25.5          |                |
|      |                                           |        |      | 16 | 32  | 32   |       |     |                | 4.91         | 25.8          |                |
|      |                                           |        |      | 32 | 16  | 16   |       |     |                | 5.01         | 25.4          |                |
|      |                                           |        |      |    | 16  |      |       |     |                | 5.16         | 25.1          | 58             |
| (B)  |                                           |        |      |    | 32  |      |       |     |                | 5.01         | 25.4          | 60             |
|      | 2                                         |        |      |    |     |      |       |     |                | 6.11         | 23.7          | 36             |
|      | 4                                         |        |      |    |     |      |       |     |                | 5.19         | 25.3          | 50             |
|      | 8                                         |        |      |    |     |      |       |     |                | 4.88         | 25.5          | 80             |
| (C)  |                                           | 256    |      |    | 32  | 32   |       |     |                | 5.75         | 24.5          | 28             |
|      |                                           | 1024   |      |    | 128 | 128  |       |     |                | 4.66         | 26.0          | 168            |
|      |                                           |        | 1024 |    |     |      |       |     |                | 5.12         | 25.4          | 53             |
|      |                                           |        | 4096 |    |     |      |       |     |                | 4.75         | 26.2          | 90             |
| (D)  |                                           |        |      |    |     |      | 0.0   |     |                | 5.77         | 24.6          |                |
|      |                                           |        |      |    |     |      | 0.2   |     |                | 4.95         | 25.5          |                |
|      |                                           |        |      |    |     |      |       | 0.0 |                | 4.67         | 25.3          |                |
|      |                                           |        |      |    |     |      |       | 0.2 |                | 5.47         | 25.7          |                |
| (E)  | positional embedding instead of sinusoids |        |      |    |     | 4.92 | 25.7  |     |                |              |               |                |
| big  | 6                                         | 1024   | 4096 | 16 |     |      | 0.3   |     | 300K           | 4.33         | 26.4          | 213            |

development set, newstest2013. We used beam search as described in the previous section, but no

In Table [3](#page-8-0) rows (A), we vary the number of attention heads and the attention key and value dimensions, keeping the amount of computation constant, as described in Section [3.2.2.](#page-3-2) While single-head attention is 0.9 BLEU worse than the best setting, quality also drops off with too many heads.

In Table [3](#page-8-0) rows (B), we observe that reducing the attention key size d<sup>k</sup> hurts model quality. This suggests that determining compatibility is not easy and that a more sophisticated compatibility function than dot product may be beneficial. We further observe in rows (C) and (D) that, as expected, bigger models are better, and dropout is very helpful in avoiding over-fitting. In row (E) we replace our sinusoidal positional encoding with learned positional embeddings [\[9\]](#page-10-9), and observe nearly identical

To evaluate if the Transformer can generalize to other tasks we performed experiments on English constituency parsing. This task presents specific challenges: the output is subject to strong structural constraints and is significantly longer than the input. Furthermore, RNN sequence-to-sequence

We trained a 4-layer transformer with dmodel = 1024 on the Wall Street Journal (WSJ) portion of the Penn Treebank [\[25\]](#page-11-12), about 40K training sentences. We also trained it in a semi-supervised setting, using the larger high-confidence and BerkleyParser corpora from with approximately 17M sentences [\[37\]](#page-11-11). We used a vocabulary of 16K tokens for the WSJ only setting and a vocabulary of 32K tokens

We performed only a small number of experiments to select the dropout, both attention and residual (section [5.4\)](#page-6-0), learning rates and beam size on the Section 22 development set, all other parameters remained unchanged from the English-to-German base translation model. During inference, we

9

models have not been able to attain state-of-the-art results in small-data regimes [\[37\]](#page-11-11).

checkpoint averaging. We present these results in Table [3.](#page-8-0)

results to the base model.

6.3 English Constituency Parsing

for the semi-supervised setting.

Table 4: The Transformer generalizes well to English constituency parsing (Results are on Section 23 of WSJ)

<span id="page-9-4"></span>

| Parser                              | Training                 | WSJ 23 F1 |
|-------------------------------------|--------------------------|-----------|
| Vinyals & Kaiser el al. (2014) [37] | WSJ only, discriminative | 88.3      |
| Petrov et al. (2006) [29]           | WSJ only, discriminative | 90.4      |
| Zhu et al. (2013) [40]              | WSJ only, discriminative | 90.4      |
| Dyer et al. (2016) [8]              | WSJ only, discriminative | 91.7      |
| Transformer (4 layers)              | WSJ only, discriminative | 91.3      |
| Zhu et al. (2013) [40]              | semi-supervised          | 91.3      |
| Huang & Harper (2009) [14]          | semi-supervised          | 91.3      |
| McClosky et al. (2006) [26]         | semi-supervised          | 92.1      |
| Vinyals & Kaiser el al. (2014) [37] | semi-supervised          | 92.1      |
| Transformer (4 layers)              | semi-supervised          | 92.7      |
| Luong et al. (2015) [23]            | multi-task               | 93.0      |
| Dyer et al. (2016) [8]              | generative               | 93.3      |

Our results in Table [4](#page-9-4) show that despite the lack of task-specific tuning our model performs surprisingly well, yielding better results than all previously reported models with the exception of the Recurrent Neural Network Grammar [\[8\]](#page-10-17).

In contrast to RNN sequence-to-sequence models [\[37\]](#page-11-11), the Transformer outperforms the Berkeley-

In this work, we presented the Transformer, the first sequence transduction model based entirely on attention, replacing the recurrent layers most commonly used in encoder-decoder architectures with

For translation tasks, the Transformer can be trained significantly faster than architectures based on recurrent or convolutional layers. On both WMT 2014 English-to-German and WMT 2014 English-to-French translation tasks, we achieve a new state of the art. In the former task our best

We are excited about the future of attention-based models and plan to apply them to other tasks. We plan to extend the Transformer to problems involving input and output modalities other than text and to investigate local, restricted attention mechanisms to efficiently handle large inputs and outputs such as images, audio and video. Making generation less sequential is another research goals of ours. The code we used to train and evaluate our models is available at [https://github.com/](https://github.com/tensorflow/tensor2tensor)

Parser [\[29\]](#page-11-13) even when training only on the WSJ training set of 40K sentences.

increased the maximum output length to input length + 300. We used a beam size of 21 and α = 0.3

for both WSJ only and the semi-supervised setting.

model outperforms even all previously reported ensembles.

7 Conclusion

multi-headed self-attention.

[tensorflow/tensor2tensor](https://github.com/tensorflow/tensor2tensor).

*[arXiv:1607.06450](http://arxiv.org/abs/1607.06450)*, 2016.

References

Acknowledgements We are grateful to Nal Kalchbrenner and Stephan Gouws for their fruitful comments, corrections and inspiration.

<span id="page-9-2"></span>[1] Jimmy Lei Ba, Jamie Ryan Kiros, and Geoffrey E Hinton. Layer normalization. *arXiv preprint*

<span id="page-9-0"></span>[2] Dzmitry Bahdanau, Kyunghyun Cho, and Yoshua Bengio. Neural machine translation by jointly

<span id="page-9-3"></span>[3] Denny Britz, Anna Goldie, Minh-Thang Luong, and Quoc V. Le. Massive exploration of neural

<span id="page-9-1"></span>[4] Jianpeng Cheng, Li Dong, and Mirella Lapata. Long short-term memory-networks for machine

10

learning to align and translate. *CoRR*, abs/1409.0473, 2014.

reading. *arXiv preprint [arXiv:1601.06733](http://arxiv.org/abs/1601.06733)*, 2016.

machine translation architectures. *CoRR*, abs/1703.03906, 2017.

<span id="page-10-2"></span>[5] Kyunghyun Cho, Bart van Merrienboer, Caglar Gulcehre, Fethi Bougares, Holger Schwenk, and Yoshua Bengio. Learning phrase representations using rnn encoder-decoder for statistical machine translation. *CoRR*, abs/1406.1078, 2014.

<span id="page-10-15"></span>[6] Francois Chollet. Xception: Deep learning with depthwise separable convolutions. *arXiv*

<span id="page-10-1"></span>[7] Junyoung Chung, Çaglar Gülçehre, Kyunghyun Cho, and Yoshua Bengio. Empirical evaluation of gated recurrent neural networks on sequence modeling. *CoRR*, abs/1412.3555, 2014.

<span id="page-10-17"></span>[8] Chris Dyer, Adhiguna Kuncoro, Miguel Ballesteros, and Noah A. Smith. Recurrent neural

<span id="page-10-9"></span>[9] Jonas Gehring, Michael Auli, David Grangier, Denis Yarats, and Yann N. Dauphin. Convolu-

<span id="page-10-13"></span>[10] Alex Graves. Generating sequences with recurrent neural networks. *arXiv preprint*

tional sequence to sequence learning. *arXiv preprint [arXiv:1705.03122v](http://arxiv.org/abs/1705.03122)2*, 2017.

*preprint [arXiv:1610.02357](http://arxiv.org/abs/1610.02357)*, 2016.

*[arXiv:1308.0850](http://arxiv.org/abs/1308.0850)*, 2013.

9(8):1735–1780, 1997.

2017.

*[arXiv:1703.10722](http://arxiv.org/abs/1703.10722)*, 2017.

*[arXiv:1703.03130](http://arxiv.org/abs/1703.03130)*, 2017.

network grammars. In *Proc. of NAACL*, 2016.

<span id="page-10-14"></span>[11] Kaiming He, Xiangyu Zhang, Shaoqing Ren, and Jian Sun. Deep residual learning for image recognition. In *Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition*, pages 770–778, 2016.

<span id="page-10-10"></span>[12] Sepp Hochreiter, Yoshua Bengio, Paolo Frasconi, and Jürgen Schmidhuber. Gradient flow in

<span id="page-10-0"></span>[13] Sepp Hochreiter and Jürgen Schmidhuber. Long short-term memory. *Neural computation*,

<span id="page-10-18"></span>[14] Zhongqiang Huang and Mary Harper. Self-training PCFG grammars with latent annotations across languages. In *Proceedings of the 2009 Conference on Empirical Methods in Natural*

<span id="page-10-4"></span>[15] Rafal Jozefowicz, Oriol Vinyals, Mike Schuster, Noam Shazeer, and Yonghui Wu. Exploring

<span id="page-10-7"></span>[16] Łukasz Kaiser and Samy Bengio. Can active memory replace attention? In *Advances in Neural*

<span id="page-10-12"></span>[17] Łukasz Kaiser and Ilya Sutskever. Neural GPUs learn algorithms. In *International Conference*

<span id="page-10-8"></span>[18] Nal Kalchbrenner, Lasse Espeholt, Karen Simonyan, Aaron van den Oord, Alex Graves, and Koray Kavukcuoglu. Neural machine translation in linear time. *arXiv preprint [arXiv:1610.10099v](http://arxiv.org/abs/1610.10099)2*,

<span id="page-10-6"></span>[19] Yoon Kim, Carl Denton, Luong Hoang, and Alexander M. Rush. Structured attention networks.

<span id="page-10-16"></span><span id="page-10-5"></span>[20] Diederik Kingma and Jimmy Ba. Adam: A method for stochastic optimization. In *ICLR*, 2015. [21] Oleksii Kuchaiev and Boris Ginsburg. Factorization tricks for LSTM networks. *arXiv preprint*

<span id="page-10-11"></span>[22] Zhouhan Lin, Minwei Feng, Cicero Nogueira dos Santos, Mo Yu, Bing Xiang, Bowen Zhou, and Yoshua Bengio. A structured self-attentive sentence embedding. *arXiv preprint*

<span id="page-10-19"></span>[23] Minh-Thang Luong, Quoc V. Le, Ilya Sutskever, Oriol Vinyals, and Lukasz Kaiser. Multi-task

sequence to sequence learning. *arXiv preprint [arXiv:1511.06114](http://arxiv.org/abs/1511.06114)*, 2015.

recurrent nets: the difficulty of learning long-term dependencies, 2001.

the limits of language modeling. *arXiv preprint [arXiv:1602.02410](http://arxiv.org/abs/1602.02410)*, 2016.

*Language Processing*, pages 832–841. ACL, August 2009.

In *International Conference on Learning Representations*, 2017.

*Information Processing Systems, (NIPS)*, 2016.

*on Learning Representations (ICLR)*, 2016.

<span id="page-10-3"></span>[24] Minh-Thang Luong, Hieu Pham, and Christopher D Manning. Effective approaches to attentionbased neural machine translation. *arXiv preprint [arXiv:1508.04025](http://arxiv.org/abs/1508.04025)*, 2015.

<span id="page-11-12"></span>[25] Mitchell P Marcus, Mary Ann Marcinkiewicz, and Beatrice Santorini. Building a large annotated corpus of english: The penn treebank. *Computational linguistics*, 19(2):313–330, 1993.

<span id="page-11-15"></span>[26] David McClosky, Eugene Charniak, and Mark Johnson. Effective self-training for parsing. In *Proceedings of the Human Language Technology Conference of the NAACL, Main Conference*,

pages 152–159. ACL, June 2006.

*preprint [arXiv:1608.05859](http://arxiv.org/abs/1608.05859)*, 2016.

2006.

Inc., 2015.

*[arXiv:1609.08144](http://arxiv.org/abs/1609.08144)*, 2016.

summarization. *arXiv preprint [arXiv:1705.04304](http://arxiv.org/abs/1705.04304)*, 2017.

with subword units. *arXiv preprint [arXiv:1508.07909](http://arxiv.org/abs/1508.07909)*, 2015.

*Advances in Neural Information Processing Systems*, 2015.

layer. *arXiv preprint [arXiv:1701.06538](http://arxiv.org/abs/1701.06538)*, 2017.

*Learning Research*, 15(1):1929–1958, 2014.

<span id="page-11-3"></span>[27] Ankur Parikh, Oscar Täckström, Dipanjan Das, and Jakob Uszkoreit. A decomposable attention model. In *Empirical Methods in Natural Language Processing*, 2016.

<span id="page-11-4"></span>[28] Romain Paulus, Caiming Xiong, and Richard Socher. A deep reinforced model for abstractive

<span id="page-11-13"></span>[29] Slav Petrov, Leon Barrett, Romain Thibaux, and Dan Klein. Learning accurate, compact, and interpretable tree annotation. In *Proceedings of the 21st International Conference on Computational Linguistics and 44th Annual Meeting of the ACL*, pages 433–440. ACL, July

<span id="page-11-6"></span>[30] Ofir Press and Lior Wolf. Using the output embedding to improve language models. *arXiv*

<span id="page-11-7"></span>[31] Rico Sennrich, Barry Haddow, and Alexandra Birch. Neural machine translation of rare words

<span id="page-11-2"></span>[32] Noam Shazeer, Azalia Mirhoseini, Krzysztof Maziarz, Andy Davis, Quoc Le, Geoffrey Hinton, and Jeff Dean. Outrageously large neural networks: The sparsely-gated mixture-of-experts

<span id="page-11-9"></span>[33] Nitish Srivastava, Geoffrey E Hinton, Alex Krizhevsky, Ilya Sutskever, and Ruslan Salakhutdinov. Dropout: a simple way to prevent neural networks from overfitting. *Journal of Machine*

<span id="page-11-5"></span>[34] Sainbayar Sukhbaatar, Arthur Szlam, Jason Weston, and Rob Fergus. End-to-end memory networks. In C. Cortes, N. D. Lawrence, D. D. Lee, M. Sugiyama, and R. Garnett, editors, *Advances in Neural Information Processing Systems 28*, pages 2440–2448. Curran Associates,

<span id="page-11-0"></span>[35] Ilya Sutskever, Oriol Vinyals, and Quoc VV Le. Sequence to sequence learning with neural networks. In *Advances in Neural Information Processing Systems*, pages 3104–3112, 2014.

<span id="page-11-10"></span>[36] Christian Szegedy, Vincent Vanhoucke, Sergey Ioffe, Jonathon Shlens, and Zbigniew Wojna. Rethinking the inception architecture for computer vision. *CoRR*, abs/1512.00567, 2015.

<span id="page-11-11"></span>[37] Vinyals & Kaiser, Koo, Petrov, Sutskever, and Hinton. Grammar as a foreign language. In

<span id="page-11-1"></span>[38] Yonghui Wu, Mike Schuster, Zhifeng Chen, Quoc V Le, Mohammad Norouzi, Wolfgang Macherey, Maxim Krikun, Yuan Cao, Qin Gao, Klaus Macherey, et al. Google's neural machine translation system: Bridging the gap between human and machine translation. *arXiv preprint*

<span id="page-11-8"></span>[39] Jie Zhou, Ying Cao, Xuguang Wang, Peng Li, and Wei Xu. Deep recurrent models with fast-forward connections for neural machine translation. *CoRR*, abs/1606.04199, 2016.

<span id="page-11-14"></span>[40] Muhua Zhu, Yue Zhang, Wenliang Chen, Min Zhang, and Jingbo Zhu. Fast and accurate shift-reduce constituent parsing. In *Proceedings of the 51st Annual Meeting of the ACL (Volume 1: Long Papers)*, pages 434–443. ACL, August 2013.

12

### Attention Visualizations **Input-Input Layer5**

![](_page_12_Figure_1.jpeg)

Figure 3: An example of the attention mechanism following long-distance dependencies in the encoder self-attention in layer 5 of 6. Many of the attention heads attend to a distant dependency of the verb 'making', completing the phrase 'making...more difficult'. Attentions here shown only for

13

the word 'making'. Different colors represent different heads. Best viewed in color.

![](_page_13_Figure_0.jpeg)

and 6. Note that the attentions are very sharp for this word.

![](_page_14_Figure_0.jpeg)

sentence. We give two such examples above, from two different heads from the encoder self-attention

15

at layer 5 of 6. The heads clearly learned to perform different tasks.
# Table 1

| Layer Type                  | Complexity per Layer   | Sequential Operations   | Maximum Path Length   |
|-----------------------------|------------------------|-------------------------|-----------------------|
| Self-Attention              | O ( n 2 · d )          | O (1)                   | O (1)                 |
| Recurrent                   | O ( n · d 2 )          | O ( n )                 | O ( n )               |
| Convolutional               | O ( k · n · d 2 )      | O (1)                   | O ( log k ( n ))      |
| Self-Attention (restricted) | O ( r · n · d )        | O (1)                   | O ( n/r )             |
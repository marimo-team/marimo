---
title: Latex
marimo-version: 0.19.6
header: |-
  # Copyright 2026 Marimo. All rights reserved.
---

```python {.marimo}
import marimo as mo
```

# LaTeX Smoke Test

This notebook tests various LaTeX writing styles and configurations.
<!---->
## 1. Inline Math Delimiters

Different ways to write inline math:
<!---->
- Dollar signs: The equation $E = mc^2$ is famous.
- Backslash parens: The equation \(E = mc^2\) also works.
- With spaces: $ a + b = c $ (spaces around content).
- Complex inline: $\frac{x^2}{y^2} + \sqrt{z}$ in a sentence.
<!---->
## 2. Display Math Delimiters

Different ways to write display/block math:
<!---->
Double dollar signs:

$$
f(x) = \int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$
<!---->
Backslash brackets:

\[
\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}
\]
<!---->
Inline display (no newlines): \[ x^2 + y^2 = z^2 \]
<!---->
## 3. LaTeX Environments
<!---->
### Align environment (multi-line equations):

\begin{align}
    B' &= -\nabla \times E \\
    E' &= \nabla \times B - 4\pi j \\
    e^{\pi i} + 1 &= 0
\end{align}
<!---->
### Equation environment:

\begin{equation}
\mathcal{L} = \int_\Omega \left( \frac{1}{2} |\nabla u|^2 - f u \right) dx
\end{equation}
<!---->
### Matrix environments:

Regular matrix: $\begin{matrix} a & b \\ c & d \end{matrix}$

Parentheses: $\begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}$

Brackets: $\begin{bmatrix} x \\ y \\ z \end{bmatrix}$

Determinant: $\begin{vmatrix} a & b \\ c & d \end{vmatrix} = ad - bc$
<!---->
### Cases environment:

$$
|x| = \begin{cases}
    x & \text{if } x \geq 0 \\
    -x & \text{if } x < 0
\end{cases}
$$
<!---->
## 4. Greek Letters and Symbols
<!---->
- Lowercase: $\alpha, \beta, \gamma, \delta, \epsilon, \zeta, \eta, \theta$
- More: $\iota, \kappa, \lambda, \mu, \nu, \xi, \pi, \rho, \sigma, \tau$
- And: $\upsilon, \phi, \chi, \psi, \omega$
- Uppercase: $\Gamma, \Delta, \Theta, \Lambda, \Xi, \Pi, \Sigma, \Phi, \Psi, \Omega$
- Operators: $\partial, \nabla, \infty, \forall, \exists, \emptyset$
- Relations: $\leq, \geq, \neq, \approx, \equiv, \sim, \propto$
- Arrows: $\leftarrow, \rightarrow, \leftrightarrow, \Rightarrow, \Leftrightarrow$
<!---->
## 5. Common Mathematical Expressions
<!---->
### Fractions and roots:

$$\frac{a}{b}, \quad \frac{x+1}{x-1}, \quad \dfrac{\partial f}{\partial x}$$

$$\sqrt{x}, \quad \sqrt[3]{x}, \quad \sqrt{x^2 + y^2}$$
<!---->
### Subscripts and superscripts:

$$x_i, \quad x^2, \quad x_i^2, \quad x_{i,j}^{(n)}, \quad e^{i\pi}$$
<!---->
### Sums, products, integrals, limits:

$$\sum_{i=1}^{n} x_i, \quad \prod_{i=1}^{n} x_i, \quad \int_a^b f(x)\,dx, \quad \lim_{x \to \infty} f(x)$$

$$\iint_D f(x,y)\,dx\,dy, \quad \oint_C \vec{F} \cdot d\vec{r}$$
<!---->
### Brackets and delimiters:

$$\left( \frac{a}{b} \right), \quad \left[ \frac{a}{b} \right], \quad \left\{ \frac{a}{b} \right\}$$

$$\left\langle \psi | \phi \right\rangle, \quad \left\| \vec{v} \right\|, \quad \left\lfloor x \right\rfloor, \quad \left\lceil x \right\rceil$$
<!---->
## 6. Chemistry (mhchem)

Using the mhchem extension for chemical equations:
<!---->
- Water: $\ce{H2O}$
- Sulfuric acid: $\ce{H2SO4}$
- Chemical reaction: $\ce{2H2 + O2 -> 2H2O}$
- Equilibrium: $\ce{N2 + 3H2 <=> 2NH3}$
- Isotopes: $\ce{^{14}C}$, $\ce{^{238}U}$
<!---->
## 7. Edge Cases
<!---->
### Math in lists:

1. First item: $a^2 + b^2 = c^2$
2. Second item: $\sin^2\theta + \cos^2\theta = 1$
3. Third item: $e^{i\theta} = \cos\theta + i\sin\theta$

- Bullet with math: $\vec{F} = m\vec{a}$
- Another: $\nabla \cdot \vec{E} = \frac{\rho}{\epsilon_0}$
<!---->
### Multiple inline math in one paragraph:

The function $f(x) = x^2$ has derivative $f'(x) = 2x$ and second derivative $f''(x) = 2$.
At $x = 0$, we have $f(0) = 0$, $f'(0) = 0$, and $f''(0) = 2 > 0$, so $x = 0$ is a local minimum.
<!---->
### Special characters that need escaping:

- Percent: $100\%$ confidence
- Ampersand in align: handled by environment
- Backslash: $\backslash$
- Tilde: $\tilde{x}$, $\widetilde{xyz}$
- Hat: $\hat{x}$, $\widehat{xyz}$
- Bar: $\bar{x}$, $\overline{xyz}$
<!---->
## 8. Real-World Examples
<!---->
### Euler's identity (the most beautiful equation):

$$e^{i\pi} + 1 = 0$$
<!---->
### Quadratic formula:

The solutions to $ax^2 + bx + c = 0$ are:

$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$
<!---->
### Gaussian integral:

$$\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}$$
<!---->
### Maxwell's equations:

\begin{align}
    \nabla \cdot \vec{E} &= \frac{\rho}{\epsilon_0} \\
    \nabla \cdot \vec{B} &= 0 \\
    \nabla \times \vec{E} &= -\frac{\partial \vec{B}}{\partial t} \\
    \nabla \times \vec{B} &= \mu_0 \vec{J} + \mu_0 \epsilon_0 \frac{\partial \vec{E}}{\partial t}
\end{align}
<!---->
### Schrödinger equation:

$$i\hbar\frac{\partial}{\partial t}\Psi(\vec{r},t) = \hat{H}\Psi(\vec{r},t) = \left[-\frac{\hbar^2}{2m}\nabla^2 + V(\vec{r},t)\right]\Psi(\vec{r},t)$$
<!---->
### Bayes' theorem:

$$P(A|B) = \frac{P(B|A) \cdot P(A)}{P(B)}$$
<!---->
### Taylor series:

$$f(x) = \sum_{n=0}^{\infty} \frac{f^{(n)}(a)}{n!}(x-a)^n = f(a) + f'(a)(x-a) + \frac{f''(a)}{2!}(x-a)^2 + \cdots$$
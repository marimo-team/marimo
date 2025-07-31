/* Copyright 2024 Marimo. All rights reserved. */

// from:
// def foo():
//    return 1/ 0
// foo()
const rawTraceback = `<div class="highlight"><pre><span></span><span class="gt">Traceback (most recent call last):</span>
  File <span class="nb">"/lib/python3.12/site-packages/marimo/_runtime/executor.py"</span>, line <span class="m">193</span>, in <span class="n">execute_cell</span>
<span class="w">    </span><span class="k">return</span> <span class="nb">eval</span><span class="p">(</span><span class="n">cell</span><span class="o">.</span><span class="n">last_expr</span><span class="p">,</span> <span class="n">glbls</span><span class="p">)</span>
<span class="w">           </span><span class="pm">^^^^^^^^^^^^^^^^^^^^^^^^^^^</span>
  File <span class="nb">"/tmp/marimo_42/__marimo__cell_Hbol_.py"</span>, line <span class="m">4</span>, in <span class="n">&lt;module&gt;</span>
<span class="w">    </span><span class="n">foo</span><span class="p">()</span>
  File <span class="nb">"/tmp/marimo_42/__marimo__cell_Hbol_.py"</span>, line <span class="m">2</span>, in <span class="n">foo</span>
<span class="w">    </span><span class="k">return</span> <span class="mi">1</span><span class="o">/</span> <span class="mi">0</span>
<span class="w">           </span><span class="pm">~^~~</span>
<span class="gr">ZeroDivisionError</span>: <span class="n">division by zero</span>
</pre></div>`;

// from:
// assert not "File /tmp/marimo_42/__marimo__cell_Hbol_.py"
const assertionTraceback = `<div class="highlight"><pre><span></span><span class="gt">Traceback (most recent call last):</span>
  File <span class="nb">"/lib/python3.12/site-packages/marimo/_runtime/executor.py"</span>, line <span class="m">192</span>, in <span class="n">execute_cell</span>
<span class="w">    </span><span class="n">exec</span><span class="p">(</span><span class="n">cell</span><span class="o">.</span><span class="n">body</span><span class="p">,</span> <span class="n">glbls</span><span class="p">)</span>
  File <span class="nb">"/tmp/marimo_42/__marimo__cell_Hbol_.py"</span>, line <span class="m">1</span>, in <span class="n">&lt;module&gt;</span>
<span class="w">    </span><span class="k">assert</span> <span class="ow">not</span> <span class="s2">"File /tmp/marimo_42/__marimo__cell_Hbol_.py"</span>
<span class="gr">AssertionError</span>
</pre></div>`;

export const Tracebacks = {
  raw: rawTraceback,
  assertion: assertionTraceback,
};

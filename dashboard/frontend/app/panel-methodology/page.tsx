export default function PanelMethodology() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">方法论</h1>
        <p className="text-muted-foreground">
          V7/V8 宏观状态分析框架完整说明
        </p>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="md:col-span-1">
          <div className="bg-card rounded-lg border p-4 sticky top-4">
            <h3 className="font-semibold mb-3">目录</h3>
            <nav className="space-y-1">
              <MethodologyLink href="#framework" label="框架总览" />
              <MethodologyLink href="#growth" label="增长维度" />
              <MethodologyLink href="#inflation" label="通胀维度" />
              <MethodologyLink href="#liquidity" label="流动性维度" />
              <MethodologyLink href="#regime" label="象限映射" />
              <MethodologyLink href="#glossary" label="术语表" />
            </nav>
          </div>
        </div>
        
        {/* Content */}
        <div className="md:col-span-3 space-y-8">
          <section id="framework" className="bg-card rounded-lg border p-6">
            <h2 className="text-xl font-bold mb-4">V7/V8 框架总览</h2>
            <div className="prose prose-sm max-w-none">
              <FrameworkOverview />
            </div>
          </section>
          
          <section id="growth" className="bg-card rounded-lg border p-6">
            <h2 className="text-xl font-bold mb-4">增长维度方法论</h2>
            <div className="prose prose-sm max-w-none">
              <GrowthMethodology />
            </div>
          </section>
          
          <section id="inflation" className="bg-card rounded-lg border p-6">
            <h2 className="text-xl font-bold mb-4">通胀维度方法论</h2>
            <div className="prose prose-sm max-w-none">
              <InflationMethodology />
            </div>
          </section>
          
          <section id="liquidity" className="bg-card rounded-lg border p-6">
            <h2 className="text-xl font-bold mb-4">流动性维度方法论</h2>
            <div className="prose prose-sm max-w-none">
              <LiquidityMethodology />
            </div>
          </section>
          
          <section id="regime" className="bg-card rounded-lg border p-6">
            <h2 className="text-xl font-bold mb-4">象限映射规则</h2>
            <div className="prose prose-sm max-w-none">
              <RegimeMapping />
            </div>
          </section>
          
          <section id="glossary" className="bg-card rounded-lg border p-6">
            <h2 className="text-xl font-bold mb-4">术语表</h2>
            <div className="prose prose-sm max-w-none">
              <Glossary />
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function MethodologyLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="block px-3 py-2 text-sm rounded-md hover:bg-muted transition-colors"
    >
      {label}
    </a>
  )
}

// Content components
function FrameworkOverview() {
  return (
    <div className="space-y-4">
      <p>
        宏观状态分析框架基于<strong>三维同构框架</strong>：增长 × 通胀 × 流动性。
        每个维度独立计算水平状态和方向趋势，最终通过优先级规则映射到10个象限。
      </p>
      
      <h3>核心原则</h3>
      <ul>
        <li><strong>水平与方向解耦</strong>：水平衡量绝对位置，方向衡量边际动态</li>
        <li><strong>逻辑完全同构</strong>：三维度严格遵循相同底层架构</li>
        <li><strong>输出分层</strong>：底层向量保留全信息，策略层映射为象限标签</li>
      </ul>
      
      <h3>处理流程</h3>
      <ol>
        <li>原始数据获取（月度/日度）</li>
        <li>HP滤波分解（周期项 + 趋势项）</li>
        <li>滚动Z-score标准化（36月窗口）</li>
        <li>自适应偏离度计算</li>
        <li>趋势方向判定（↑/↓/→）</li>
        <li>维度状态合成（水平 + 方向）</li>
        <li>象限映射（10级优先级）</li>
      </ol>
    </div>
  )
}

function GrowthMethodology() {
  return (
    <div className="space-y-4">
      <h3>输入指标</h3>
      <ul>
        <li><strong>制造业PMI</strong>：绝对零点法（50为荣枯线）</li>
        <li><strong>工业增加值同比</strong>：HP滤波 + Z-score</li>
        <li><strong>非制造业PMI</strong>：结构性防误判仲裁</li>
      </ul>
      
      <h3>PMI绝对零点法</h3>
      <p>Z = (PMI - 50) / rolling_std(PMI - 50, 36)</p>
      <p>趋势项固定为50（荣枯线），避免长期中枢下移导致偏离度失真。</p>
      
      <h3>水平判定</h3>
      <ul>
        <li>PMI ≥ 50：扩张</li>
        <li>PMI < 50：收缩</li>
        <li>IAV周期项 ≥ 0：扩张</li>
        <li>IAV周期项 < 0：收缩</li>
      </ul>
      
      <h3>方向判定</h3>
      <p>基于Z-score偏离度与自适应阈值比较：</p>
      <ul>
        <li>偏离度 > 阈值：↑（上行）</li>
        <li>偏离度 < -阈值：↓（下行）</li>
        <li>否则：→（平稳）</li>
      </ul>
    </div>
  )
}

function InflationMethodology() {
  return (
    <div className="space-y-4">
      <h3>输入指标</h3>
      <ul>
        <li><strong>核心CPI同比</strong>：原始同比定水平</li>
        <li><strong>PPI同比</strong>：HP滤波定方向</li>
      </ul>
      
      <h3>水平判定（基于核心CPI）</h3>
      <ul>
        <li>CPI > 3%：高通胀</li>
        <li>1% ≤ CPI ≤ 3%：温和通胀</li>
        <li>CPI < 1%：低通胀</li>
      </ul>
      
      <h3>方向判定（基于PPI + CPI）</h3>
      <ul>
        <li>两者同向：取该方向</li>
        <li>一平稳一方向：取方向</li>
        <li>两者反向：→（平稳）</li>
      </ul>
      
      <h3>WARNING：成本传导背离</h3>
      <p>当CPI与PPI方向相反时触发，提示上下游利润可能重塑。</p>
    </div>
  )
}

function LiquidityMethodology() {
  return (
    <div className="space-y-4">
      <h3>输入指标</h3>
      <ul>
        <li><strong>M2同比</strong>：HP滤波 + Z-score</li>
        <li><strong>社融存量同比</strong>：HP滤波 + Z-score</li>
        <li><strong>DR007</strong>：日频数据，价格方向仲裁</li>
        <li><strong>OMO利率</strong>：央行意图识别</li>
      </ul>
      
      <h3>水平判定</h3>
      <ul>
        <li>M2周期项 ≥ 0：货币扩张</li>
        <li>M2周期项 < 0：货币收缩</li>
        <li>社融周期项 ≥ 0：信用扩张</li>
        <li>社融周期项 < 0：信用收缩</li>
      </ul>
      
      <h3>状态组合</h3>
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b">
            <th className="text-left p-2">M2</th>
            <th className="text-left p-2">社融</th>
            <th className="text-left p-2">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-b">
            <td className="p-2">扩张</td>
            <td className="p-2">扩张</td>
            <td className="p-2">双宽</td>
          </tr>
          <tr className="border-b">
            <td className="p-2">扩张</td>
            <td className="p-2">收缩</td>
            <td className="p-2">宽货币紧信用</td>
          </tr>
          <tr className="border-b">
            <td className="p-2">收缩</td>
            <td className="p-2">扩张</td>
            <td className="p-2">紧货币宽信用</td>
          </tr>
          <tr>
            <td className="p-2">收缩</td>
            <td className="p-2">收缩</td>
            <td className="p-2">双紧</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

function RegimeMapping() {
  return (
    <div className="space-y-4">
      <p>10级优先级象限映射（P1最高优先级 → P10最低）：</p>
      
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b bg-muted">
            <th className="text-left p-2">优先级</th>
            <th className="text-left p-2">象限</th>
            <th className="text-left p-2">增长</th>
            <th className="text-left p-2">通胀</th>
            <th className="text-left p-2">流动性</th>
          </tr>
        </thead>
        <tbody>
          {[
            { p: 'P1', regime: '极端滞胀', g: '收缩', i: '高通胀', l: '双紧' },
            { p: 'P2', regime: '典型滞胀', g: '收缩/中性下行', i: '高通胀', l: '非双紧' },
            { p: 'P3', regime: '过热期', g: '扩张', i: '高通胀', l: '非双紧' },
            { p: 'P4', regime: '失速衰退', g: '收缩', i: '低通胀', l: '双紧' },
            { p: 'P5', regime: '宽衰退', g: '收缩/中性下行', i: '低通胀', l: '宽松' },
            { p: 'P6', regime: '弱复苏', g: '扩张/中性上行', i: '低通胀', l: '宽松' },
            { p: 'P7', regime: '强势复苏', g: '扩张', i: '温和/低通胀', l: '宽松' },
            { p: 'P8', regime: '完美扩张', g: '扩张', i: '温和通胀', l: '非双紧' },
            { p: 'P9', regime: '类衰退过渡', g: '中性', i: '低通胀', l: '双紧' },
            { p: 'P10', regime: '震荡/观望', g: '其他', i: '其他', l: '其他' },
          ].map((row) => (
            <tr key={row.p} className="border-b hover:bg-muted/50">
              <td className="p-2 font-mono">{row.p}</td>
              <td className="p-2 font-semibold">{row.regime}</td>
              <td className="p-2">{row.g}</td>
              <td className="p-2">{row.i}</td>
              <td className="p-2">{row.l}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Glossary() {
  return (
    <div className="space-y-4">
      <dl className="space-y-2">
        <div>
          <dt className="font-semibold">HP滤波（Hodrick-Prescott Filter）</dt>
          <dd className="text-sm text-muted-foreground">
            一种时间序列分解方法，将序列分解为趋势项和周期项。本项目使用单边HP滤波（λ=129600，月度），避免未来函数问题。
          </dd>
        </div>
        
        <div>
          <dt className="font-semibold">Z-score</dt>
          <dd className="text-sm text-muted-foreground">
            标准化得分，表示当前值距离历史均值有多少个标准差。Z > 0表示高于历史平均，Z < 0表示低于历史平均。
          </dd>
        </div>
        
        <div>
          <dt className="font-semibold">周期项（Cycle）</dt>
          <dd className="text-sm text-muted-foreground">
            HP滤波分解出的短期波动成分，反映经济周期中的波动。
          </dd>
        </div>
        
        <div>
          <dt className="font-semibold">趋势项（Trend）</dt>
          <dd className="text-sm text-muted-foreground">
            HP滤波分解出的长期趋势成分，反映经济的长期走向。
          </dd>
        </div>
        
        <div>
          <dt className="font-semibold">偏离度（Deviation）</dt>
          <dd className="text-sm text-muted-foreground">
            Z-score与其3月移动平均的差，用于判断短期趋势变化。
          </dd>
        </div>
        
        <div>
          <dt className="font-semibold">自适应阈值</dt>
          <dd className="text-sm text-muted-foreground">
            基于滚动标准差动态调整的阈值（±1.0×σ），用于判断方向变化。
          </dd>
        </div>
      </dl>
    </div>
  )
}

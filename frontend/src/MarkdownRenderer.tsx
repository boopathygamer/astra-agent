import React, { useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Check } from 'lucide-react';

interface MarkdownRendererProps {
    content: string;
}

// ── Copy Button for Code Blocks ──
function CopyButton({ text }: { text: string }) {
    const [copied, setCopied] = useState(false);

    const handleCopy = useCallback(async () => {
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // fallback
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    }, [text]);

    return (
        <button
            onClick={handleCopy}
            className="md-copy-btn"
            title={copied ? 'Copied!' : 'Copy code'}
        >
            {copied ? (
                <>
                    <Check className="w-3.5 h-3.5" />
                    <span>Copied!</span>
                </>
            ) : (
                <>
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copy</span>
                </>
            )}
        </button>
    );
}

// ── Language display names ──
const LANG_NAMES: Record<string, string> = {
    js: 'JavaScript', javascript: 'JavaScript', jsx: 'JSX',
    ts: 'TypeScript', typescript: 'TypeScript', tsx: 'TSX',
    py: 'Python', python: 'Python',
    rb: 'Ruby', ruby: 'Ruby',
    java: 'Java', cpp: 'C++', c: 'C', cs: 'C#',
    go: 'Go', rust: 'Rust', rs: 'Rust',
    html: 'HTML', css: 'CSS', scss: 'SCSS', sass: 'Sass',
    json: 'JSON', yaml: 'YAML', yml: 'YAML', toml: 'TOML',
    xml: 'XML', sql: 'SQL', graphql: 'GraphQL',
    bash: 'Bash', sh: 'Shell', zsh: 'Zsh', powershell: 'PowerShell', ps1: 'PowerShell',
    md: 'Markdown', markdown: 'Markdown',
    dockerfile: 'Dockerfile', docker: 'Docker',
    swift: 'Swift', kotlin: 'Kotlin', dart: 'Dart',
    php: 'PHP', r: 'R', lua: 'Lua', perl: 'Perl',
    text: 'Text', txt: 'Text', plaintext: 'Text',
};

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
    return (
        <div className="markdown-body">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    // ── Code Blocks & Inline Code ──
                    code({ className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '');
                        const lang = match?.[1] || '';
                        const codeString = String(children).replace(/\n$/, '');
                        const isInline = !match && !codeString.includes('\n');

                        if (isInline) {
                            return (
                                <code className="md-inline-code" {...props}>
                                    {children}
                                </code>
                            );
                        }

                        const displayLang = LANG_NAMES[lang.toLowerCase()] || lang.toUpperCase() || 'Code';

                        return (
                            <div className="md-code-block">
                                <div className="md-code-header">
                                    <div className="md-code-lang">
                                        <span className="md-code-dot">{'</>'}</span>
                                        {displayLang}
                                    </div>
                                    <CopyButton text={codeString} />
                                </div>
                                <SyntaxHighlighter
                                    style={oneDark}
                                    language={lang || 'text'}
                                    PreTag="div"
                                    customStyle={{
                                        margin: 0,
                                        padding: '16px 20px',
                                        background: 'transparent',
                                        fontSize: '13px',
                                        lineHeight: '1.6',
                                        borderRadius: '0 0 12px 12px',
                                    }}
                                    codeTagProps={{
                                        style: {
                                            fontFamily: '"JetBrains Mono", ui-monospace, monospace',
                                        },
                                    }}
                                >
                                    {codeString}
                                </SyntaxHighlighter>
                            </div>
                        );
                    },

                    // ── Headings ──
                    h1({ children }) {
                        return <h1 className="md-h1">{children}</h1>;
                    },
                    h2({ children }) {
                        return <h2 className="md-h2">{children}</h2>;
                    },
                    h3({ children }) {
                        return <h3 className="md-h3">{children}</h3>;
                    },
                    h4({ children }) {
                        return <h4 className="md-h4">{children}</h4>;
                    },

                    // ── Paragraph ──
                    p({ children }) {
                        return <p className="md-p">{children}</p>;
                    },

                    // ── Lists ──
                    ul({ children }) {
                        return <ul className="md-ul">{children}</ul>;
                    },
                    ol({ children }) {
                        return <ol className="md-ol">{children}</ol>;
                    },
                    li({ children }) {
                        return <li className="md-li">{children}</li>;
                    },

                    // ── Blockquote (Output blocks) ──
                    blockquote({ children }) {
                        return <blockquote className="md-blockquote">{children}</blockquote>;
                    },

                    // ── Table ──
                    table({ children }) {
                        return (
                            <div className="md-table-wrap">
                                <table className="md-table">{children}</table>
                            </div>
                        );
                    },
                    thead({ children }) {
                        return <thead className="md-thead">{children}</thead>;
                    },
                    tbody({ children }) {
                        return <tbody className="md-tbody">{children}</tbody>;
                    },
                    tr({ children }) {
                        return <tr className="md-tr">{children}</tr>;
                    },
                    th({ children }) {
                        return <th className="md-th">{children}</th>;
                    },
                    td({ children }) {
                        return <td className="md-td">{children}</td>;
                    },

                    // ── Links ──
                    a({ href, children }) {
                        return (
                            <a href={href} target="_blank" rel="noopener noreferrer" className="md-link">
                                {children}
                            </a>
                        );
                    },

                    // ── Strong / Em ──
                    strong({ children }) {
                        return <strong className="md-strong">{children}</strong>;
                    },
                    em({ children }) {
                        return <em className="md-em">{children}</em>;
                    },

                    // ── Horizontal Rule ──
                    hr() {
                        return <hr className="md-hr" />;
                    },

                    // ── Pre (wrapping code blocks) ──
                    pre({ children }) {
                        return <>{children}</>;
                    },
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}

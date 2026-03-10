import React, { createContext, useContext, useState, useEffect, ReactNode, useRef } from 'react';
import { CreateMLCEngine, InitProgressReport, MLCEngineInterface } from '@mlc-ai/web-llm';

// Using a lightweight but capable coder model for fast browser interaction
const SELECTED_MODEL = 'Llama-3-8B-Instruct-q4f32_1-MLC';

// Expose globally for offline api.ts fallback
declare global {
    interface Window {
        _webLlmEngine?: MLCEngineInterface | null;
    }
}

interface WebLLMContextType {
    engine: MLCEngineInterface | null;
    isLoaded: boolean;
    isLoading: boolean;
    progressText: string;
    loadModel: () => Promise<void>;
    generateResponse: (prompt: string, onUpdate?: (text: string) => void) => Promise<string>;
}

const WebLLMContext = createContext<WebLLMContextType | undefined>(undefined);

export const WebLLMProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [engine, setEngine] = useState<MLCEngineInterface | null>(null);
    const [isLoaded, setIsLoaded] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [progressText, setProgressText] = useState('Not loaded.');

    // We use a ref to prevent strict mode double-loading in dev
    const isInitializing = useRef(false);

    const loadModel = async () => {
        if (isLoaded || isInitializing.current) return;

        isInitializing.current = true;
        setIsLoading(true);
        setProgressText('Initializing WebGPU Engine...');

        try {
            const initProgressCallback = (report: InitProgressReport) => {
                setProgressText(report.text);
            };

            const newEngine = await CreateMLCEngine(
                SELECTED_MODEL,
                { initProgressCallback }
            );

            setEngine(newEngine);
            window._webLlmEngine = newEngine; // Expose globally
            setIsLoaded(true);
            setProgressText('Model Loaded and Ready.');
        } catch (error) {
            console.error("Failed to load WebLLM model:", error);
            setProgressText('Expansion failed. WebGPU not supported or network error.');
        } finally {
            setIsLoading(false);
            isInitializing.current = false;
        }
    };

    const generateResponse = async (prompt: string, onUpdate?: (text: string) => void): Promise<string> => {
        if (!engine) {
            throw new Error("WebLLM Engine is not loaded yet.");
        }

        const messages: import('@mlc-ai/web-llm').ChatCompletionMessageParam[] = [
            { role: "system", content: "You are the Astra Edge Agent. You run locally in the user's browser. You are an expert at coding, architecture, and hyper-optimized logic." },
            { role: "user", content: prompt }
        ];

        try {
            if (onUpdate) {
                // Streaming mode
                const chunks = await engine.chat.completions.create({
                    messages,
                    stream: true,
                });

                let fullReply = "";
                for await (const chunk of chunks) {
                    const content = chunk.choices[0]?.delta?.content || "";
                    fullReply += content;
                    if (onUpdate) onUpdate(fullReply);
                }
                return fullReply;
            } else {
                // Sync mode
                const reply = await engine.chat.completions.create({
                    messages,
                });
                return reply.choices[0].message.content || "";
            }
        } catch (err) {
            console.error("Inference Error:", err);
            return "Execution failed. Edge core overloaded.";
        }
    };

    return (
        <WebLLMContext.Provider value={{
            engine,
            isLoaded,
            isLoading,
            progressText,
            loadModel,
            generateResponse
        }}>
            {children}
        </WebLLMContext.Provider>
    );
};

export const useWebLLM = () => {
    const context = useContext(WebLLMContext);
    if (context === undefined) {
        throw new Error('useWebLLM must be used within a WebLLMProvider');
    }
    return context;
};

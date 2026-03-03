import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';

export default function WebDevPage() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white p-6">
      <header className="mb-8">
        <Link to="/chat" className="inline-flex items-center gap-2 text-white/50 hover:text-white transition-colors">
          <ArrowLeft className="w-5 h-5" />
          <span>Back to Chat</span>
        </Link>
      </header>
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-4">Web Dev</h1>
        {/* Empty page content */}
      </div>
    </div>
  );
}

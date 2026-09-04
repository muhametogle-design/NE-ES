import React, { useState } from 'react';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { Search, ShieldCheck, GraduationCap, Building2 } from 'lucide-react';

export function StateLookup() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    try {
      setLoading(true);
      setHasSearched(true);
      const data = await api.searchStateStudents(query);
      setResults(data || []);
    } catch (e) {
      console.error(e);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">National Student Registry Lookup</h2>
        <p className="text-xs text-slate-500">Cross-institutional search by Name or National Roll Number</p>
      </div>

      <Card>
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="flex-1">
            <Input
              placeholder="Search by student first name, surname, or Roll Number (e.g., IL-10001)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
          </div>
          <Button type="submit" loading={loading} className="flex items-center gap-1.5">
            <Search className="h-4 w-4" /> Search Registry
          </Button>
        </form>
      </Card>

      {/* Results */}
      <Card title="Search Results" subtitle={hasSearched ? `Found ${results.length} matched records` : 'Enter a query above'}>
        {loading ? (
          <div className="py-8 text-center text-xs text-slate-400">Searching national registry database...</div>
        ) : hasSearched && results.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400">No student records found matching "{query}"</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500 font-bold uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Roll Number (NE-SID)</th>
                  <th className="px-4 py-3">Student Name</th>
                  <th className="px-4 py-3">Gender</th>
                  <th className="px-4 py-3">School</th>
                  <th className="px-4 py-3">Grade Level</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {results.map((r, idx) => (
                  <tr key={idx} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono font-bold text-slate-900">{r.roll_number}</td>
                    <td className="px-4 py-3 font-semibold text-slate-800">{r.first_name} {r.last_name}</td>
                    <td className="px-4 py-3 text-slate-600">{r.gender}</td>
                    <td className="px-4 py-3 text-slate-700 font-medium">
                      <span className="font-bold mr-1">[{r.school_code}]</span> {r.school_name}
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {r.class_level ? `Grade ${r.class_level} (${r.stream})` : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={r.is_active ? 'success' : 'danger'}>
                        {r.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

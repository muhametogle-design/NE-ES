import React, { useState, useEffect } from 'react';
import { useDispatch } from 'react-redux';
import { api } from '../api/client';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Select, Input } from '../components/ui/Input';
import { Badge } from '../components/ui/Badge';
import { ProgressMeter } from '../components/ui/ProgressMeter';
import { addToast } from '../features/ui/uiSlice';
import { BookOpen, CheckCircle, Plus, Calendar, AlertTriangle } from 'lucide-react';

export function Syllabus() {
  const dispatch = useDispatch();

  const [plans, setPlans] = useState([]);
  const [classes, setClasses] = useState([]);
  const [subjects, setSubjects] = useState([]);
  const [loading, setLoading] = useState(true);

  const [selectedPlan, setSelectedPlan] = useState(null);
  const [newTopic, setNewTopic] = useState({ unit_number: 1, title: '', description: '' });
  const [progressNotes, setProgressNotes] = useState('');
  const [selectedTopicId, setSelectedTopicId] = useState(null);

  const loadPlans = async () => {
    try {
      setLoading(true);
      const data = await api.getSyllabusPlans();
      setPlans(data || []);
      if (data && data.length > 0 && !selectedPlan) {
        setSelectedPlan(data[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const loadDependencies = async () => {
    try {
      const [cls, subs] = await Promise.all([api.getClasses(), api.getSubjects()]);
      setClasses(cls || []);
      setSubjects(subs || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadDependencies();
    loadPlans();
  }, []);

  const handleAddTopic = async (e) => {
    e.preventDefault();
    if (!selectedPlan || !newTopic.title) return;
    try {
      await api.createSyllabusTopic({
        plan_id: selectedPlan.id,
        unit_number: parseInt(newTopic.unit_number),
        title: newTopic.title,
        description: newTopic.description,
      });
      dispatch(addToast({ type: 'success', message: 'Topic added to syllabus plan' }));
      setNewTopic({ unit_number: (selectedPlan.topics?.length || 0) + 1, title: '', description: '' });
      // Reload plans
      const updatedPlans = await api.getSyllabusPlans();
      setPlans(updatedPlans);
      const active = updatedPlans.find((p) => p.id === selectedPlan.id);
      setSelectedPlan(active);
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    }
  };

  const handleRecordProgress = async (topicId) => {
    try {
      await api.recordSyllabusProgress({
        topic_id: topicId,
        date_covered: new Date().toISOString().split('T')[0],
        notes: progressNotes || 'Topic covered and completed according to standard curriculum guidelines.',
      });
      dispatch(addToast({ type: 'success', message: 'Topic completion marked!' }));
      setSelectedTopicId(null);
      setProgressNotes('');
      const updatedPlans = await api.getSyllabusPlans();
      setPlans(updatedPlans);
      const active = updatedPlans.find((p) => p.id === selectedPlan.id);
      setSelectedPlan(active);
    } catch (err) {
      dispatch(addToast({ type: 'error', message: err.message }));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900">Curriculum Pacing & Syllabus Tracker</h2>
        <p className="text-xs text-slate-500">Monitor unit coverage progress against midterm and final targets</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Plans List */}
        <Card title="Active Course Plans" subtitle="Select a plan to view syllabus topics">
          <div className="space-y-2 max-h-[500px] overflow-y-auto">
            {plans.map((p) => {
              const isSelected = selectedPlan?.id === p.id;
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setSelectedPlan(p)}
                  className={`w-full p-3 rounded-xl border text-left transition-all ${
                    isSelected
                      ? 'border-emerald-500 bg-emerald-50/50 shadow-xs'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-bold text-slate-900 text-xs truncate">{p.subject_name}</h4>
                    <Badge variant={p.status === 'completed' ? 'success' : p.status === 'on_track' ? 'info' : 'danger'}>
                      {p.status?.replace('_', ' ')}
                    </Badge>
                  </div>
                  <ProgressMeter
                    value={p.completed_units}
                    max={p.total_units}
                    label={p.class_name}
                    color={p.status === 'behind' ? 'rose' : 'emerald'}
                  />
                </button>
              );
            })}
          </div>
        </Card>

        {/* Selected Plan Details & Topics */}
        <div className="lg:col-span-2 space-y-6">
          {selectedPlan ? (
            <>
              <Card
                title={`${selectedPlan.subject_name} — ${selectedPlan.class_name}`}
                subtitle={`Target: Midterm ${selectedPlan.midterm_target}% • Final ${selectedPlan.final_target}%`}
              >
                <div className="space-y-4">
                  <ProgressMeter
                    value={selectedPlan.completed_units}
                    max={selectedPlan.total_units}
                    label={`Completed Units: ${selectedPlan.completed_units} / ${selectedPlan.total_units}`}
                    color={selectedPlan.status === 'behind' ? 'rose' : 'emerald'}
                  />

                  {/* Topics List */}
                  <div className="space-y-2 pt-2">
                    <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500">Curriculum Units</h5>
                    {selectedPlan.topics?.length === 0 ? (
                      <p className="text-xs text-slate-400 py-4 text-center">No units defined yet for this course</p>
                    ) : (
                      <div className="space-y-2">
                        {selectedPlan.topics?.map((topic) => (
                          <div
                            key={topic.id}
                            className={`p-3 rounded-xl border flex items-center justify-between text-xs ${
                              topic.is_completed
                                ? 'bg-emerald-50/40 border-emerald-200'
                                : 'bg-white border-slate-200'
                            }`}
                          >
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-slate-900">Unit {topic.unit_number}: {topic.title}</span>
                                {topic.is_completed ? (
                                  <Badge variant="success" size="sm">Completed</Badge>
                                ) : (
                                  <Badge variant="default" size="sm">Pending</Badge>
                                )}
                              </div>
                              {topic.description && <p className="text-slate-500 mt-0.5">{topic.description}</p>}
                            </div>

                            <div>
                              {!topic.is_completed ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleRecordProgress(topic.id)}
                                >
                                  Mark Completed
                                </Button>
                              ) : (
                                <span className="text-emerald-700 font-bold flex items-center gap-1 text-[11px]">
                                  <CheckCircle className="h-3.5 w-3.5" /> Covered
                                </span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </Card>

              {/* Add New Unit Form */}
              <Card title="Add Syllabus Unit" subtitle="Define next topic in the pacing plan">
                <form onSubmit={handleAddTopic} className="space-y-3">
                  <div className="grid grid-cols-4 gap-3">
                    <Input
                      label="Unit #"
                      type="number"
                      value={newTopic.unit_number}
                      onChange={(e) => setNewTopic({ ...newTopic, unit_number: e.target.value })}
                      className="w-full"
                    />
                    <div className="col-span-3">
                      <Input
                        label="Unit Title"
                        placeholder="e.g. Chapter 4: Linear Algebra"
                        value={newTopic.title}
                        onChange={(e) => setNewTopic({ ...newTopic, title: e.target.value })}
                        required
                      />
                    </div>
                  </div>
                  <Input
                    label="Description / Learning Objectives"
                    placeholder="Key concepts, experiments, or exercises..."
                    value={newTopic.description}
                    onChange={(e) => setNewTopic({ ...newTopic, description: e.target.value })}
                  />
                  <div className="flex justify-end pt-1">
                    <Button type="submit" size="sm">
                      <Plus className="h-3.5 w-3.5 mr-1" /> Add Unit
                    </Button>
                  </div>
                </form>
              </Card>
            </>
          ) : (
            <Card>
              <div className="py-12 text-center text-xs text-slate-400">Select a course plan to view syllabus topics</div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

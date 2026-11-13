"""Five-neighbor level estimation, with explicit abstention and evidence.

No AI, fitting of labels, eval, or symbolic execution. This first adapter uses
bounded LaTeX source-structure features, not semantic expression AST features.
It is therefore an experimental baseline, not a completed PLAN.md level gate.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from statistics import pstdev

from scripts.audit_bank import classify

FEATURE_NAMES = ('problem_nodes', 'nesting_depth', 'distinct_functions', 'key_nodes')
FUNCTIONS = frozenset(('sin','cos','tan','sec','csc','cot','arcsin','arccos','arctan','ln','log','exp','sqrt','sinh','cosh','tanh'))
TOKEN = re.compile(r'\\[A-Za-z]+|\d+(?:\.\d+)?|[A-Za-z]|[^\s]')
MAX_TEXT = 4000
MAX_DEPTH = 40
K = 5


class FeatureError(ValueError):
    pass


def normalize(text: str) -> str:
    return ' '.join(text.split())


def family_key(statement: str) -> str:
    """Conservative leakage group: same number-masked statement, across topics.

    Does not establish mathematical equivalence. All exact/whitespace duplicates
    and detected number variants stay in one evaluation fold.
    """
    text = re.sub(r'\d+(?:\.\d+)?', '<N>', normalize(statement))
    return hashlib.sha256(text.encode()).hexdigest()


def structure(text: str) -> tuple[int,int,set[str]]:
    if not isinstance(text,str) or not text.strip() or len(text)>MAX_TEXT:
        raise FeatureError('Expected non-empty bounded math text')
    tokens=TOKEN.findall(text)
    stack=[];maximum=0;functions=set();nodes=0
    for token in tokens:
        if token in ('{','('):
            stack.append(token);maximum=max(maximum,len(stack))
            if maximum>MAX_DEPTH:raise FeatureError('Math text is nested too deeply')
        elif token in ('}',')'):
            opener='{' if token=='}' else '('
            if not stack or stack.pop()!=opener:raise FeatureError('Unbalanced math delimiters')
        elif token not in (r'\left',r'\right',r'\displaystyle',r'\,',r'\!'):
            nodes+=1
            if token.startswith('\\') and token[1:] in FUNCTIONS:functions.add(token[1:])
    if stack:raise FeatureError('Unbalanced math delimiters')
    if not nodes:raise FeatureError('No usable math tokens')
    return nodes,maximum,functions


def features(statement: str, key_latex: str) -> tuple[float,...]:
    if not isinstance(statement,str) or len(statement)>MAX_TEXT:
        raise FeatureError('Problem statement exceeds input limits')
    # Statements use single-dollar math. Prose is not counted as mathematical size.
    if statement.count('$')%2:raise FeatureError('Unbalanced math delimiters')
    fragments=re.findall(r'\$([^$]+)\$',statement)
    if not fragments:raise FeatureError('Problem needs explicit dollar-delimited math')
    problem=[structure(part) for part in fragments]
    key=structure(re.sub(r'\s*\+\s*C\s*$','',key_latex))
    functions=set().union(*(item[2] for item in problem),key[2])
    return float(sum(item[0] for item in problem)),float(max([item[1] for item in problem]+[key[1]])),float(len(functions)),float(key[0])


@dataclass(frozen=True)
class Reference:
    topic: str
    problem_id: str
    level: int
    statement: str
    key_latex: str
    vector: tuple[float,...]
    family: str


def prepare(bank: list[dict]) -> tuple[list[Reference],list[dict]]:
    records=[];excluded=[];seen=set()
    for problem in bank:
        reason=classify(problem)
        ref=f"{problem['topic']}::{problem['id']}"
        if reason:
            excluded.append({'reference':ref,'reason':reason});continue
        identity=(problem['topic'],str(problem['id']))
        if identity in seen:
            excluded.append({'reference':ref,'reason':'duplicate_topic_id'});continue
        seen.add(identity)
        answer=problem.get('answer') or {}
        try:vector=features(problem['statement'],answer.get('latex',''))
        except FeatureError as error:
            excluded.append({'reference':ref,'reason':str(error)});continue
        records.append(Reference(problem['topic'],str(problem['id']),int(problem['level']),problem['statement'],answer['latex'],vector,family_key(problem['statement'])))
    return records,excluded


class LevelGuesser:
    def __init__(self,references: list[Reference]):
        self.references=tuple(references)
        self.by_topic={topic:tuple(r for r in references if r.topic==topic) for topic in {r.topic for r in references}}

    def estimate(self,topic: str,statement: str,key_latex: str,*,exclude_families=()) -> dict:
        try:vector=features(statement,key_latex)
        except (FeatureError,TypeError) as error:
            return self._abstain('unsupported_input',str(error))
        # Prevent a known example or a trivial number variant from serving as its own evidence.
        excluded=set(exclude_families)|{family_key(statement)}
        pool=[r for r in self.by_topic.get(topic,()) if r.family not in excluded]
        if len(pool)<K:return self._abstain('insufficient_neighbors',f'Need {K} other reference problems in this topic; found {len(pool)}')
        # Fit scales to the available reference pool only. Test labels/features never enter scales.
        scales=[pstdev([r.vector[j] for r in pool]) or 1.0 for j in range(len(FEATURE_NAMES))]
        ranked=sorted(pool,key=lambda r:(sum(((a-b)/scale)**2 for a,b,scale in zip(vector,r.vector,scales)),r.topic,r.problem_id))
        neighbors=ranked[:K]
        # Equal distances straddling the cutoff make membership depend on arbitrary IDs.
        # Abstain rather than invent certainty from that ordering.
        def distance(r):return math.sqrt(sum(((a-b)/scale)**2 for a,b,scale in zip(vector,r.vector,scales)))
        cutoff_tie=len(ranked)>K and math.isclose(distance(ranked[K-1]),distance(ranked[K]),rel_tol=1e-12,abs_tol=1e-12)
        votes=Counter(r.level for r in neighbors)
        winner,count=votes.most_common(1)[0]
        status='estimated' if count>=3 and not cutoff_tie else 'neighbor_boundary_tie' if cutoff_tie else 'no_majority'
        return {'status':status,'estimated_level':winner if status=='estimated' else None,
                'reason':'Strict majority of five nearest same-topic references' if status=='estimated' else 'No unambiguous majority-based estimate',
                'votes':{str(k):v for k,v in sorted(votes.items())},'vote_fraction':count/K,
                'features':dict(zip(FEATURE_NAMES,vector)),
                'neighbors':[{'topic':r.topic,'id':r.problem_id,'level':r.level,'distance':round(distance(r),6)} for r in neighbors],
                'warning':'Experimental source-structure baseline; votes are not calibrated confidence or proof of difficulty.'}

    def check_requested_level(self,topic: str,statement: str,key_latex: str,requested_level: int) -> dict:
        if type(requested_level) is not int or requested_level not in (1,2,3,4):
            raise ValueError('requested_level must be an integer from 1 to 4')
        family=family_key(statement) if isinstance(statement,str) else ''
        available=sum(r.level==requested_level and r.family!=family for r in self.by_topic.get(topic,()))
        if available<K:
            result=self._abstain('insufficient_requested_level_pool',f'Requested level has only {available} independent reference rows; need {K}; use labeled bank fallback')
        else:result=self.estimate(topic,statement,key_latex)
        result.update(requested_level=requested_level,passes_requested_level=result['status']=='estimated' and result['estimated_level']==requested_level)
        return result

    @staticmethod
    def _abstain(status,reason):
        return {'status':status,'estimated_level':None,'reason':reason,'neighbors':[],'votes':{},'vote_fraction':None}

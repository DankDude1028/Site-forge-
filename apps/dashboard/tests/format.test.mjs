import { test } from 'node:test';
import assert from 'node:assert/strict';
import {rows,dollars,readable} from '../src/format.mjs';
test('malformed resources remain empty and cannot invent metrics',()=>{assert.deepEqual(rows({error:'offline'}),[]);assert.deepEqual(rows(null),[]);assert.equal(dollars(undefined),'$0.00');});
test('API list envelopes and money values are supported',()=>{assert.deepEqual(rows({items:[{id:1}]}),[{id:1}]);assert.equal(dollars('1234.50'),'$1,234.50');assert.equal(readable('waiting_approval'),'waiting approval');});

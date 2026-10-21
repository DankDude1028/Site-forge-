import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
test('owner session displays missing economics honestly and gates approval review',async({page})=>{
  await page.route('**/v1/**',route=>{
    const path=new URL(route.request().url()).pathname;
    const resources={sites:[{id:'site-1',slug:'label-planner',status:'preview'}],workers:[{id:'worker-1',name:'Windows GPU',status:'online',version:'0.1.0'}],tasks:[{id:'task-1',agent_type:'research',status:'completed',attempt:1,capability:'read_sources'}],approvals:[{id:'approval-1',site_id:'site-1',action:'deploy_production',amount:'0',currency:'USD',status:'pending',payload_hash:'fixture-immutable-hash',payload:{commit:'abc123'}}]};
    const key=path.split('/')[2];
    const value=path.endsWith('/economics')?{verified_revenue:null,verified_expenses:null}:resources[key]??[];
    return route.fulfill({json:value});
  });
  await page.goto('/');
  await page.getByLabel('Supervisor access token').fill('fixture-ui-token');
  await page.getByRole('button',{name:'Open control room'}).click();
  await expect(page.getByRole('heading',{name:'Portfolio',exact:true})).toBeVisible();
  await expect(page.getByText('Awaiting provider imports')).toBeVisible();
  await expect(page.getByText('label-planner',{exact:true})).toBeVisible();
  await page.screenshot({path:'../../runtime/dashboard-desktop.png',fullPage:true});
  const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa']).analyze();
  expect(results.violations).toEqual([]);
  await page.getByRole('button',{name:'Approvals'}).click();
  await page.getByRole('button',{name:'Review details'}).click();
  await expect(page.getByRole('dialog')).toContainText('fixture-immutable-hash');
  await expect(page.getByRole('button',{name:'Approve exact action'})).toBeVisible();
  await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.getByRole('button',{name:'End session'}).click();
  await expect(page.getByLabel('Supervisor access token')).toHaveValue('');
});
test('login is usable at narrow widths',async({page})=>{
  await page.setViewportSize({width:390,height:844});await page.goto('/');
  await expect(page.getByRole('heading',{level:1})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});

test('older pending approvals and jobs beyond the first page remain visible',async({page})=>{
  let pendingFilterUsed=false;
  await page.route('**/v1/**',route=>{
    const url=new URL(route.request().url());const key=url.pathname.split('/')[2];
    let value=[];
    if(key==='dashboard-summary')value={sites:0,workers:0,tasks:101,pending_approvals:1,audit_events:0};
    if(key==='tasks'){
      const offset=Number(url.searchParams.get('offset')??0);
      value=Array.from({length:offset===0?100:1},(_,i)=>({id:`task-${offset+i}`,agent_type:'research',status:'completed',attempt:1,capability:'read_sources'}));
    }
    if(key==='approvals'){
      pendingFilterUsed=url.searchParams.get('status')==='pending';
      value=[{id:'old-pending',site_id:'site-1',action:'deploy_production',status:'pending',amount:'0',currency:'USD'}];
    }
    return route.fulfill({json:value});
  });
  await page.goto('/');await page.getByLabel('Supervisor access token').fill('fixture-ui-token');
  await page.getByRole('button',{name:'Open control room'}).click();
  await expect(page.getByText('Pending across all records')).toBeVisible();
  expect(pendingFilterUsed).toBe(true);
  await page.getByRole('button',{name:'Agents & jobs'}).click();
  await expect(page.getByText('Showing 1–100 of 101')).toBeVisible();
  await page.getByRole('button',{name:'Next tasks',exact:true}).click();
  await expect(page.getByText('task-100',{exact:true})).toBeVisible();
  await expect(page.getByText('Showing 101–101 of 101')).toBeVisible();
  await expect(page.getByRole('button',{name:'Next tasks',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Approvals'}).click();
  await expect(page.getByRole('button',{name:'Review details'})).toBeVisible();
});

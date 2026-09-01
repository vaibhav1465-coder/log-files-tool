"use client";

import { createContext, useContext, useEffect, useState, type FormEvent, type ReactNode } from "react";

export type AppUser = { id:string; email:string; display_name:string; role:"analyst"|"admin"; active:boolean; must_change_password:boolean };
type AuthContextValue = { user:AppUser; refresh:()=>Promise<void>; logout:()=>Promise<void> };
const AuthContext=createContext<AuthContextValue|null>(null);
const apiUrl=(process.env.NEXT_PUBLIC_API_URL??"").replace(/\/$/,"");

export function useAuth(){
  const value=useContext(AuthContext);
  if(!value)throw new Error("useAuth must be used inside AuthShell");
  return value;
}

export default function AuthShell({children}:{children:ReactNode}){
  const [user,setUser]=useState<AppUser|null>(null);
  const [checking,setChecking]=useState(true);
  const [email,setEmail]=useState("vaibhav.singh@indianexpress.com");
  const [password,setPassword]=useState("");
  const [error,setError]=useState("");
  const [submitting,setSubmitting]=useState(false);
  const [currentPassword,setCurrentPassword]=useState("");
  const [newPassword,setNewPassword]=useState("");
  const [confirmPassword,setConfirmPassword]=useState("");

  async function refresh(){
    const response=await fetch(`${apiUrl}/api/v1/auth/me`,{credentials:"include",cache:"no-store"});
    setUser(response.ok?(await response.json() as {user:AppUser}).user:null);
  }
  useEffect(()=>{refresh().finally(()=>setChecking(false));},[]);

  async function login(event:FormEvent){
    event.preventDefault();setSubmitting(true);setError("");
    try{
      const response=await fetch(`${apiUrl}/api/v1/auth/login`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({email,password})});
      const body=await response.json().catch(()=>({detail:"Login failed"})) as {user?:AppUser;detail?:string};
      if(!response.ok||!body.user)throw new Error(body.detail??"Login failed");
      setUser(body.user);setPassword("");
    }catch(reason){setError(reason instanceof Error?reason.message:"Login failed");}
    finally{setSubmitting(false);}
  }

  async function changePassword(event:FormEvent){
    event.preventDefault();setSubmitting(true);setError("");
    try{
      if(newPassword!==confirmPassword)throw new Error("New passwords do not match.");
      if(newPassword===currentPassword)throw new Error("Choose a password different from the temporary password.");
      const response=await fetch(`${apiUrl}/api/v1/auth/change-password`,{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({current_password:currentPassword,new_password:newPassword})});
      const body=await response.json().catch(()=>({detail:"Password change failed"})) as {detail?:string};
      if(!response.ok)throw new Error(body.detail??"Password change failed");
      setCurrentPassword("");setNewPassword("");setConfirmPassword("");await refresh();
    }catch(reason){setError(reason instanceof Error?reason.message:"Password change failed");}
    finally{setSubmitting(false);}
  }

  async function logout(){
    await fetch(`${apiUrl}/api/v1/auth/logout`,{method:"POST",credentials:"include"});
    setUser(null);
  }

  if(checking)return <div className="authLoading"><span className="loader"/>Checking your secure session…</div>;
  if(!user)return <main className="loginPage">
    <section className="loginStory">
      <div className="brandLockup"><span>EI</span><div><strong>Express Intelligence</strong><small>Financial Express pilot</small></div></div>
      <div><p className="eyebrow light">PRIVATE NEWSROOM OPERATIONS</p><h1>Turn delivery logs into decisions.</h1><p>Read approved Financial Express CDN logs without downloading source files or opening the AWS console.</p></div>
      <ul><li>VPN-only server</li><li>Read-only S3 access</li><li>Named sessions and complete audit trail</li></ul>
    </section>
    <section className="loginCard">
      <div><p className="eyebrow">SECURE ACCESS</p><h2>Sign in to continue</h2><p>Use the account created by your administrator. AWS and VPN passwords are never accepted here.</p></div>
      <form onSubmit={login} className="loginForm">
        <label>Email address<input type="email" value={email} onChange={event=>setEmail(event.target.value)} autoComplete="username" required/></label>
        <label>Password<input type="password" value={password} onChange={event=>setPassword(event.target.value)} autoComplete="current-password" minLength={12} required/></label>
        {error&&<div className="formError" role="alert">{error}</div>}
        <button className="primaryButton" disabled={submitting}>{submitting?"Signing in…":"Sign in"}</button>
      </form>
      <small className="privacyCopy">Sessions expire after 12 hours. Connect to the company VPN before signing in.</small>
    </section>
  </main>;

  if(user.must_change_password)return <main className="loginPage"><section className="loginStory"><div className="brandLockup"><span>EI</span><div><strong>Express Intelligence</strong><small>Secure account setup</small></div></div><div><p className="eyebrow light">TEMPORARY PASSWORD</p><h1>Create your private password.</h1><p>Your temporary password must be replaced before any logs or analysis tools can be accessed.</p></div><ul><li>Use at least 12 characters</li><li>Do not reuse AWS, VPN, or email passwords</li><li>Only a one-way password hash is stored</li></ul></section><section className="loginCard"><div><p className="eyebrow">REQUIRED SECURITY STEP</p><h2>Change temporary password</h2></div><form onSubmit={changePassword} className="loginForm"><label>Temporary password<input type="password" value={currentPassword} onChange={event=>setCurrentPassword(event.target.value)} autoComplete="current-password" minLength={12} required/></label><label>New password<input type="password" value={newPassword} onChange={event=>setNewPassword(event.target.value)} autoComplete="new-password" minLength={12} required/></label><label>Confirm new password<input type="password" value={confirmPassword} onChange={event=>setConfirmPassword(event.target.value)} autoComplete="new-password" minLength={12} required/></label>{error&&<div className="formError" role="alert">{error}</div>}<button className="primaryButton" disabled={submitting}>{submitting?"Changing…":"Change password and continue"}</button></form></section></main>;

  return <AuthContext.Provider value={{user,refresh,logout}}>{children}</AuthContext.Provider>;
}

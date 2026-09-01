"use client";
import { useAuth } from "./auth-shell";

export default function WorkspaceHeader(){
 const {user,logout}=useAuth();
 return <div className="workspaceBar"><div><span className="liveDot"/>Private pilot online</div><div className="userMenu"><span><strong>{user.display_name}</strong><small>{user.role}</small></span><button onClick={()=>void logout()}>Log out</button></div></div>;
}

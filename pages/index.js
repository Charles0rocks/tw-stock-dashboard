import fs from 'fs';
import path from 'path';

export default function Home() {
  return null;
}

export async function getServerSideProps({ res }) {
  const candidatePaths = [
    path.join(process.cwd(), 'public', 'index.html'),
    path.join(process.cwd(), 'index.html'),
    path.join(__dirname, '..', 'public', 'index.html'),
    path.join(__dirname, '..', '..', 'public', 'index.html'),
  ];

  let html = null;
  for (const p of candidatePaths) {
    try {
      if (fs.existsSync(p)) {
        html = fs.readFileSync(p, 'utf8');
        if (html && html.includes('<!DOCTYPE html>')) break;
      }
    } catch (e) {}
  }

  if (html) {
    res.setHeader('Content-Type', 'text/html; charset=utf-8');
    res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate, max-age=0');
    res.write(html);
    res.end();
  } else {
    res.statusCode = 500;
    res.setHeader('Content-Type', 'text/plain; charset=utf-8');
    res.end('Error: index.html not found on server.');
  }

  return { props: {} };
}

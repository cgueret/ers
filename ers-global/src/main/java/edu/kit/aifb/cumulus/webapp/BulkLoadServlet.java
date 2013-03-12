package edu.kit.aifb.cumulus.webapp;

import java.io.IOException;
import java.io.PrintWriter;
import java.util.Iterator;
import java.util.logging.Logger;
import java.util.StringTokenizer;
import java.util.HashMap;
import java.util.List;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.FileOutputStream;
import java.io.File;
import java.util.UUID;

import javax.servlet.ServletContext;
import javax.servlet.ServletException;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

import org.semanticweb.yars.nx.Node;
import org.semanticweb.yars.nx.Resource;
import org.semanticweb.yars.nx.parser.NxParser;
import org.semanticweb.yars.nx.parser.ParseException;

import edu.kit.aifb.cumulus.store.Store;
import edu.kit.aifb.cumulus.store.AbstractCassandraRdfHector;
import edu.kit.aifb.cumulus.store.StoreException;
import edu.kit.aifb.cumulus.webapp.formatter.SerializationFormat;

import org.apache.commons.fileupload.servlet.ServletFileUpload;
import org.apache.commons.fileupload.FileItemFactory; 
import org.apache.commons.fileupload.FileUploadException;
import org.apache.commons.fileupload.disk.DiskFileItemFactory;
import org.apache.commons.fileupload.FileItem;

/** 
 * @author tmacicas
 */
@SuppressWarnings("serial")
public class BulkLoadServlet extends AbstractHttpServlet {
	private final Logger _log = Logger.getLogger(this.getClass().getName());

	@Override
	public void doPost(HttpServletRequest req, HttpServletResponse resp) throws IOException, ServletException {
		long start = System.currentTimeMillis();
		ServletContext ctx = getServletContext();
		if (req.getCharacterEncoding() == null)
			req.setCharacterEncoding("UTF-8");
		resp.setCharacterEncoding("UTF-8");

		String accept = req.getHeader("Accept");
		SerializationFormat formatter = Listener.getSerializationFormat(accept);
		if (formatter == null) {
			sendError(ctx, req, resp, HttpServletResponse.SC_NOT_ACCEPTABLE, "no known mime type in Accept header");
			return;
		}
		PrintWriter out_r = resp.getWriter();
		String resp_msg = "";
		// check that we have a file upload request
		boolean isMultipart = ServletFileUpload.isMultipartContent(req);
		if( ! isMultipart ) { 
			sendError(ctx, req, resp, HttpServletResponse.SC_NOT_ACCEPTABLE, "no file upload");
			return;
		}
		// Create a factory for disk-based file items
		FileItemFactory factory = new DiskFileItemFactory();
		// Create a new file upload handler
		ServletFileUpload upload = new ServletFileUpload(factory);
		// Parse the request
		try {
			List<FileItem> items = upload.parseRequest(req);
			// bulk load options
			int threads = -1;
			String format = "nt";
			int batchSizeMB = 1;
			//get store
			AbstractCassandraRdfHector crdf = (AbstractCassandraRdfHector)ctx.getAttribute(Listener.STORE);
			crdf.setBatchSize(batchSizeMB);

			// Process the uploaded items
			Iterator iter = items.iterator();
			while (iter.hasNext()) {
			    FileItem item = (FileItem) iter.next();
			    if (item.isFormField()) {
				// skip 
			    } else {
				   String fieldName = item.getFieldName();
				   String fileName = item.getName();
				   String contentType = item.getContentType();
				   boolean isInMemory = item.isInMemory();
				   long sizeInBytes = item.getSize();
				   // Process a file upload
				   InputStream uploadedStream = item.getInputStream();
				   // write the inputStream to a FileOutputStream
			           String file = "/tmp/upload_bulkload_"+UUID.randomUUID();
  			  	   OutputStream out = new FileOutputStream(new File(file));
				   int read = 0;
				   byte[] bytes = new byte[1024];
				   while ((read = uploadedStream.read(bytes)) != -1) {
					out.write(bytes, 0, read);
				   }
				   uploadedStream.close();
				   out.flush();
			  	   out.close();
				   // load here 
				   crdf.bulkLoad(new File(file), format, threads);
				   resp_msg += "[dataset] POST bulk load " + fileName + ", size " + sizeInBytes + ", time " + (System.currentTimeMillis() - start) + "ms "; 
				   _log.info("[dataset] POST bulk load " + fileName + ", size " + sizeInBytes + ", time " + (System.currentTimeMillis() - start) + "ms ");
				   // delete the tmp file 
				   new File(file).delete();
			    }
			}
		} catch(FileUploadException ex) { 
			ex.printStackTrace(); 
			return;
		} catch(StoreException ex) { 
			ex.printStackTrace(); 
			return;
		}
		out_r.println(resp_msg);
		out_r.close();
		return;
	}
	
	@Override
	public void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException, ServletException {
		throw new UnsupportedOperationException("GET currently not supported, sorry.");
	}	
	public void doDelete(HttpServletRequest req, HttpServletResponse resp) throws IOException, ServletException {
		throw new UnsupportedOperationException("DELETE currently not supported, sorry.");
	}
	public void doPut(HttpServletRequest req, HttpServletResponse resp) throws IOException, ServletException {
		throw new UnsupportedOperationException("PUT currently not supported, sorry.");
	}
}
"""Service for executing real trades on Polymarket using py-clob-client."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module, util
from typing import Optional

from polly.models import Market

# USDC contracts on Polygon
USDC_CONTRACT_ADDRESS = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Native USDC
USDC_E_CONTRACT_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # Bridged USDC.e
# Polymarket CTF Exchange contract
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"
POLYGON_RPC_URL = "https://polygon-rpc.com"

# ERC20 ABI for approve function
ERC20_APPROVE_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]


@dataclass
class TradeExecutionResult:
    """Result of a trade execution attempt."""

    success: bool
    order_id: Optional[str]
    error: Optional[str]
    executed_price: float
    executed_size: float


class TradingService:
    """Service for executing real trades on Polymarket."""

    def __init__(self, private_key: str, chain_id: int, host: str, signature_type: int = 1, funder: str = ""):
        """Initialize trading service with wallet credentials.

        Args:
            private_key: Polygon wallet private key
            chain_id: Blockchain chain ID (137 for Polygon)
            host: CLOB API host URL
            signature_type: Signature type (1 for direct wallet, 2 for browser wallet)
            funder: Polymarket proxy/funder address
        """
        self.host = host
        self.chain_id = chain_id
        self.signature_type = signature_type
        self.funder = funder
        self._private_key = private_key
        
        # Derive wallet address from private key
        eth_account = import_module("eth_account")
        Account = getattr(eth_account, "Account")
        account = Account.from_key(private_key)
        self._address = account.address
        
        self._client = self._create_authenticated_client(private_key)
    
    def approve_allowance(self) -> tuple[bool, str]:
        """Approve USDC allowance for Polymarket trading.
        
        This sends an on-chain transaction that grants the Polymarket
        exchange contract permission to spend your USDC tokens.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            print("[DEBUG] Attempting to approve USDC allowance on-chain...")
            
            # Import web3
            try:
                web3_module = import_module("web3")
                Web3 = getattr(web3_module, "Web3")
            except (ImportError, AttributeError):
                return (False, "web3.py not installed. Run: pip install web3")
            
            # Connect to Polygon
            w3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL))
            if not w3.is_connected():
                return (False, f"Failed to connect to Polygon RPC: {POLYGON_RPC_URL}")
            
            print(f"[DEBUG] Connected to Polygon. Chain ID: {w3.eth.chain_id}")
            
            # Get account from private key
            eth_account = import_module("eth_account")
            Account = getattr(eth_account, "Account")
            account = Account.from_key(self._private_key)
            
            # Max uint256 for unlimited approval
            max_approval = 2**256 - 1
            
            # Approve both USDC and USDC.e to be safe (from EOA wallet)
            print(f"[DEBUG] Approving from EOA wallet: {account.address[:10]}...")
            
            contracts_to_approve = [
                ("USDC.e (bridged)", USDC_E_CONTRACT_ADDRESS),
                ("USDC (native)", USDC_CONTRACT_ADDRESS)
            ]
            
            last_tx_hash = None
            for token_name, token_address in contracts_to_approve:
                print(f"[DEBUG] Approving {token_name} spending for CTF Exchange...")
                
                usdc_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=ERC20_APPROVE_ABI
                )
                
                # Build approve transaction from the EOA
                approve_txn = usdc_contract.functions.approve(
                    Web3.to_checksum_address(CTF_EXCHANGE_ADDRESS),
                    max_approval
                ).build_transaction({
                    'from': account.address,  # Sign from EOA, not proxy
                    'nonce': w3.eth.get_transaction_count(account.address),
                    'gas': 100000,  # Standard gas limit for approve
                    'gasPrice': w3.eth.gas_price,
                    'chainId': self.chain_id
                })
                
                print(f"[DEBUG] Signing {token_name} transaction...")
                signed_txn = account.sign_transaction(approve_txn)
                
                print(f"[DEBUG] Sending {token_name} transaction to Polygon...")
                tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
                last_tx_hash = tx_hash
                
                print(f"[DEBUG] Transaction sent! Hash: {tx_hash.hex()}")
                print(f"[DEBUG] Waiting for confirmation...")
                
                # Wait for transaction receipt (with timeout)
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                
                if receipt['status'] == 1:
                    print(f"[DEBUG] ✓ {token_name} approval confirmed! Block: {receipt['blockNumber']}")
                else:
                    return (False, f"{token_name} approval transaction failed. Tx: {tx_hash.hex()}")
            
            return (True, f"USDC/USDC.e allowances approved! Last Tx: {last_tx_hash.hex()[:16]}...")
                
        except Exception as e:
            error_msg = f"Failed to approve allowance: {type(e).__name__}: {str(e)}"
            print(f"[DEBUG] {error_msg}")
            return (False, error_msg)

    def _create_authenticated_client(self, private_key: str):
        """Create authenticated CLOB client for trading."""
        if util.find_spec("py_clob_client.client") is None:
            raise RuntimeError("py-clob-client not installed; required for real trading.")

        module = import_module("py_clob_client.client")
        client_class = getattr(module, "ClobClient")

        # Create client based on signature_type and funder
        if self.funder and self.signature_type > 0:
            # Proxy mode (signature_type 1 or 2)
            print(f"[DEBUG] Initializing ClobClient with signature_type={self.signature_type}, funder={self.funder[:10]}...")
            try:
                client = client_class(
                    self.host,
                    key=private_key,
                    chain_id=self.chain_id,
                    signature_type=self.signature_type,
                    funder=self.funder
                )
                print(f"[DEBUG] ClobClient initialized in PROXY mode")
            except Exception as init_error:
                print(f"[DEBUG] Client init error: {init_error}")
                raise
        else:
            # Direct EOA mode (no proxy)
            print(f"[DEBUG] Initializing ClobClient in Direct EOA mode (full trading access)")
            client = client_class(self.host, key=private_key, chain_id=self.chain_id)

        # Set up API credentials for authenticated requests
        try:
            print(f"[DEBUG] Creating API credentials...")
            creds = client.create_or_derive_api_creds()
            print(f"[DEBUG] Setting API credentials...")
            client.set_api_creds(creds)
            print(f"[DEBUG] API credentials set successfully")
        except Exception as cred_error:
            print(f"[DEBUG] Credentials error: {cred_error}")
            raise

        return client

    def execute_market_buy_with_amount(self, token_id: str, stake_amount: float) -> TradeExecutionResult:
        """Execute a market buy order with a specific stake amount.
        
        This method fetches the current orderbook price and calculates the appropriate
        number of shares to buy with the given stake amount.

        Args:
            token_id: Token ID to purchase
            stake_amount: Amount of USDC to spend

        Returns:
            TradeExecutionResult with execution details
        """
        try:
            # Import order types
            clob_types = import_module("py_clob_client.clob_types")
            constants = import_module("py_clob_client.order_builder.constants")

            OrderArgs = getattr(clob_types, "OrderArgs")
            OrderType = getattr(clob_types, "OrderType")
            BUY = getattr(constants, "BUY")

            # Get current orderbook to determine market price
            print(f"[DEBUG] Full token_id: {token_id}")
            print(f"[DEBUG] Fetching orderbook for token_id: {token_id[:16]}...")
            
            orderbook = self._client.get_order_book(token_id)
            print(f"[DEBUG] Orderbook response type: {type(orderbook)}")
            print(f"[DEBUG] Orderbook keys: {orderbook.keys() if isinstance(orderbook, dict) else 'not a dict'}")
            
            best_ask = self._get_best_ask(orderbook)

            if best_ask is None:
                # Debug: check what we got back
                if hasattr(orderbook, 'asks'):
                    asks_count = len(orderbook.asks) if orderbook.asks else 0
                elif isinstance(orderbook, dict):
                    asks_count = len(orderbook.get("asks", []))
                else:
                    asks_count = 0
                
                return TradeExecutionResult(
                    success=False,
                    order_id=None,
                    error=f"No liquidity available (token_id: {token_id[:16]}..., asks: {asks_count})",
                    executed_price=0.0,
                    executed_size=0.0,
                )

            # Calculate shares based on actual orderbook price with 2% slippage
            price = min(best_ask * 1.02, 0.99)
            
            # Ensure stake meets Polymarket's $1 minimum
            if stake_amount < 1.0:
                print(f"[DEBUG] Stake ${stake_amount:.2f} is below $1 minimum, adjusting to $1.01")
                stake_amount = 1.01
            
            # Calculate shares - add small buffer to ensure we meet minimum
            size = (stake_amount + 0.01) / price  # Add 1 cent buffer for rounding
            
            print(f"[DEBUG] Calculated: stake=${stake_amount:.2f}, price=${price:.4f}, size={size:.4f} shares, total=${size*price:.4f}")
            
            # Create limit order
            return self.execute_market_buy(token_id, size)
            
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'message'):
                error_msg = e.message
            elif hasattr(e, 'args') and e.args:
                error_msg = str(e.args[0])
            
            return TradeExecutionResult(
                success=False,
                order_id=None,
                error=f"Exception during trade execution: {type(e).__name__}: {error_msg}",
                executed_price=0.0,
                executed_size=0.0,
            )
    
    def execute_market_buy(self, token_id: str, size: float) -> TradeExecutionResult:
        """Execute a market buy order.

        Args:
            token_id: Token ID to purchase
            size: Number of shares to buy

        Returns:
            TradeExecutionResult with execution details
        """
        try:
            # Import order types
            clob_types = import_module("py_clob_client.clob_types")
            constants = import_module("py_clob_client.order_builder.constants")

            OrderArgs = getattr(clob_types, "OrderArgs")
            OrderType = getattr(clob_types, "OrderType")
            BUY = getattr(constants, "BUY")

            # Get current orderbook to determine market price
            # Token IDs from Polymarket API are decimal strings, use as-is
            print(f"[DEBUG] Full token_id: {token_id}")
            print(f"[DEBUG] Fetching orderbook for token_id: {token_id[:16]}...")
            
            orderbook = self._client.get_order_book(token_id)
            print(f"[DEBUG] Orderbook response type: {type(orderbook)}")
            print(f"[DEBUG] Orderbook keys: {orderbook.keys() if isinstance(orderbook, dict) else 'not a dict'}")
            
            best_ask = self._get_best_ask(orderbook)

            if best_ask is None:
                # Debug: check what we got back
                if hasattr(orderbook, 'asks'):
                    asks_count = len(orderbook.asks) if orderbook.asks else 0
                elif isinstance(orderbook, dict):
                    asks_count = len(orderbook.get("asks", []))
                else:
                    asks_count = 0
                
                return TradeExecutionResult(
                    success=False,
                    order_id=None,
                    error=f"No liquidity available (token_id: {token_id[:16]}..., asks: {asks_count})",
                    executed_price=0.0,
                    executed_size=0.0,
                )

            # Create limit order slightly above best ask to ensure fill (market order simulation)
            # Add 2% slippage tolerance, capped at 0.99
            price = min(best_ask * 1.02, 0.99)

            # Create order arguments (use original decimal format for order creation)
            order_args = OrderArgs(
                price=price,
                size=size,
                side=BUY,
                token_id=token_id,  # Use original format
            )

            # Ensure API credentials are set (refresh if needed)
            try:
                print(f"[DEBUG] Refreshing API credentials...")
                creds = self._client.create_or_derive_api_creds()
                self._client.set_api_creds(creds)
            except Exception as cred_error:
                print(f"[DEBUG] Warning: Could not refresh credentials: {cred_error}")
            
            # Note: We'll handle allowances if we get an error during order posting
            
            # Sign the order
            signed_order = self._client.create_order(order_args)
            
            # Debug: print order details
            print(f"[DEBUG] Posting BUY order: price={price:.4f}, size={size:.2f}, token_id={token_id[:16]}...")
            print(f"[DEBUG] Order side: BUY, best_ask was: {best_ask:.4f}")

            # Post as Good-Till-Cancelled order
            try:
                resp = self._client.post_order(signed_order, OrderType.GTC)
                print(f"[DEBUG] Order post response: {resp}")
            except Exception as post_error:
                # Extract more details from the error
                error_detail = str(post_error)
                print(f"[DEBUG] Full post_error: {post_error}")
                print(f"[DEBUG] Error type: {type(post_error)}")
                print(f"[DEBUG] Error attributes: {dir(post_error)}")
                
                # Try to extract error details from PolyApiException
                if hasattr(post_error, 'status_code'):
                    print(f"[DEBUG] Status code: {post_error.status_code}")
                if hasattr(post_error, 'error_message'):
                    print(f"[DEBUG] Error message: {post_error.error_message}")
                    # Extract actual error from dict if available
                    if isinstance(post_error.error_message, dict):
                        actual_error = post_error.error_message.get('error', error_detail)
                        error_detail = actual_error
                if hasattr(post_error, 'message'):
                    print(f"[DEBUG] Message: {post_error.message}")
                if hasattr(post_error, 'args'):
                    print(f"[DEBUG] Args: {post_error.args}")
                
                # Handle allowance error with automatic approval
                if "balance / allowance" in error_detail or "allowance" in error_detail.lower():
                    print(f"\n[yellow]USDC allowance required. Attempting to approve...[/yellow]")
                    print(f"[dim]This is a one-time on-chain transaction (costs ~$0.01 in gas)[/dim]\n")
                    
                    allowance_ok, allowance_msg = self.approve_allowance()
                    
                    if allowance_ok:
                        print(f"\n[green]✓ Allowance approved successfully![/green]")
                        print(f"[dim]Waiting for blockchain state to propagate...[/dim]")
                        
                        # Give the blockchain a moment to propagate the allowance
                        import time
                        time.sleep(5)
                        
                        print(f"[dim]Retrying trade...[/dim]\n")
                        
                        # Retry the order post
                        try:
                            resp = self._client.post_order(signed_order, OrderType.GTC)
                            print(f"[DEBUG] Retry order post response: {resp}")
                            
                            # Check response
                            if isinstance(resp, dict):
                                success = resp.get("success", False)
                                order_id = resp.get("orderID")
                                error = resp.get("error")
                                if error and not success:
                                    error = f"{error} | Response: {resp}"
                            else:
                                success = False
                                order_id = None
                                error = f"Unexpected response type: {type(resp)}"
                            
                            return TradeExecutionResult(
                                success=success,
                                order_id=order_id,
                                error=error,
                                executed_price=price,
                                executed_size=size,
                            )
                        except Exception as retry_error:
                            # Get detailed error for retry failure
                            retry_detail = str(retry_error)
                            print(f"[DEBUG] Retry error: {retry_error}")
                            print(f"[DEBUG] Retry error type: {type(retry_error)}")
                            if hasattr(retry_error, 'error_message'):
                                print(f"[DEBUG] Retry error message: {retry_error.error_message}")
                                if isinstance(retry_error.error_message, dict):
                                    retry_detail = retry_error.error_message.get('error', retry_detail)
                            
                            # If still allowance issue after approval, might need more time or different approach
                            if "allowance" in retry_detail.lower():
                                retry_detail = f"{retry_detail}. The approval was confirmed on-chain but Polymarket's API may need more time. Wait 30 seconds and try again, or try placing the order directly on polymarket.com to verify the approval worked."
                            
                            return TradeExecutionResult(
                                success=False,
                                order_id=None,
                                error=f"Trade retry failed: {retry_detail}",
                                executed_price=0.0,
                                executed_size=0.0,
                            )
                    else:
                        error_detail = f"Failed to approve USDC allowance: {allowance_msg}"
                
                # Provide helpful error messages for other errors
                elif "403" in error_detail or "Cloudflare" in error_detail:
                    error_detail = "Cloudflare blocked request (403). Using VPN may help."
                elif "invalid amount" in error_detail or "min size" in error_detail:
                    # Already a clear error from API
                    pass
                
                return TradeExecutionResult(
                    success=False,
                    order_id=None,
                    error=f"{error_detail}",
                    executed_price=0.0,
                    executed_size=0.0,
                )

            # Check response (handle both dict and exception cases)
            if isinstance(resp, dict):
                success = resp.get("success", False)
                order_id = resp.get("orderID")
                error = resp.get("error")
                # If error in response, include full response for debugging
                if error and not success:
                    error = f"{error} | Response: {resp}"
            else:
                success = False
                order_id = None
                error = f"Unexpected response type: {type(resp)}"

            return TradeExecutionResult(
                success=success,
                order_id=order_id,
                error=error,
                executed_price=price,
                executed_size=size,
            )

        except Exception as e:
            # Get detailed error message
            error_msg = str(e)
            # Try to extract more details if it's a PolyApiException
            if hasattr(e, 'message'):
                error_msg = e.message
            elif hasattr(e, 'args') and e.args:
                error_msg = str(e.args[0])
            
            return TradeExecutionResult(
                success=False,
                order_id=None,
                error=f"Exception during trade execution: {type(e).__name__}: {error_msg}",
                executed_price=0.0,
                executed_size=0.0,
            )

    def execute_market_sell(self, token_id: str, size: float) -> TradeExecutionResult:
        """Execute a market sell order (close position).

        Args:
            token_id: Token ID to sell
            size: Number of shares to sell

        Returns:
            TradeExecutionResult with execution details
        """
        try:
            # Import order types
            clob_types = import_module("py_clob_client.clob_types")
            constants = import_module("py_clob_client.order_builder.constants")

            OrderArgs = getattr(clob_types, "OrderArgs")
            OrderType = getattr(clob_types, "OrderType")
            SELL = getattr(constants, "SELL")

            # Get current orderbook to determine market price
            # Token IDs from Polymarket API are decimal strings, use as-is
            orderbook = self._client.get_order_book(token_id)
            
            # Debug output
            print(f"[DEBUG] Fetching orderbook for SELL token_id: {token_id[:16]}...")
            
            best_bid = self._get_best_bid(orderbook)

            if best_bid is None:
                # Debug: check what we got back
                if hasattr(orderbook, 'bids'):
                    bids_count = len(orderbook.bids) if orderbook.bids else 0
                elif isinstance(orderbook, dict):
                    bids_count = len(orderbook.get("bids", []))
                else:
                    bids_count = 0
                
                return TradeExecutionResult(
                    success=False,
                    order_id=None,
                    error=f"No liquidity available (token_id: {token_id[:16]}..., bids: {bids_count})",
                    executed_price=0.0,
                    executed_size=0.0,
                )

            # Create limit order slightly below best bid to ensure fill
            # Subtract 2% slippage tolerance, floored at 0.01
            price = max(best_bid * 0.98, 0.01)

            # Create order arguments (use original decimal format for order creation)
            order_args = OrderArgs(
                price=price,
                size=size,
                side=SELL,
                token_id=token_id,  # Use original format
            )

            # Sign the order
            signed_order = self._client.create_order(order_args)

            # Post as Good-Till-Cancelled order
            resp = self._client.post_order(signed_order, OrderType.GTC)

            # Check response (handle both dict and exception cases)
            if isinstance(resp, dict):
                success = resp.get("success", False)
                order_id = resp.get("orderID")
                error = resp.get("error")
                # If error in response, include full response for debugging
                if error and not success:
                    error = f"{error} | Response: {resp}"
            else:
                success = False
                order_id = None
                error = f"Unexpected response type: {type(resp)}"

            return TradeExecutionResult(
                success=success,
                order_id=order_id,
                error=error,
                executed_price=price,
                executed_size=size,
            )

        except Exception as e:
            # Get detailed error message
            error_msg = str(e)
            # Try to extract more details if it's a PolyApiException
            if hasattr(e, 'message'):
                error_msg = e.message
            elif hasattr(e, 'args') and e.args:
                error_msg = str(e.args[0])
            
            return TradeExecutionResult(
                success=False,
                order_id=None,
                error=f"Exception during sell execution: {type(e).__name__}: {error_msg}",
                executed_price=0.0,
                executed_size=0.0,
            )

    def get_balances(self) -> dict:
        """Get wallet balances (USDC and positions).

        Returns:
            Dictionary with balance information (usdc, address)
        """
        try:
            # Try using Polymarket API to get balance first
            if hasattr(self._client, 'get_balance_allowance'):
                try:
                    print(f"[DEBUG] Fetching balance from Polymarket API...")
                    balance_data = self._client.get_balance_allowance()
                    print(f"[DEBUG] API balance data: {balance_data}")
                    # Extract USDC balance from response
                    if isinstance(balance_data, dict):
                        usdc_balance = float(balance_data.get('balance', 0)) / 1_000_000  # Convert from wei
                        return {
                            "usdc": usdc_balance,
                            "address": self.funder if self.funder else self._address
                        }
                except Exception as api_error:
                    print(f"[DEBUG] API balance fetch failed: {api_error}, falling back to RPC...")
            
            # Fallback to RPC check
            import requests
            
            # Check address based on trading mode
            # Direct EOA: use main wallet address
            # Proxy mode: use proxy/funder address
            check_address = self.funder if (self.funder and self.signature_type > 0) else self._address
            
            # Check both USDC and USDC.e (bridged) balances
            total_balance = 0.0
            
            for token_name, token_address in [("USDC", USDC_CONTRACT_ADDRESS), ("USDC.e", USDC_E_CONTRACT_ADDRESS)]:
                # Query token balance using Polygon RPC
                # ERC20 balanceOf signature: 0x70a08231 + padded address
                data = f"0x70a08231000000000000000000000000{check_address[2:].lower()}"
                
                payload = {
                    "jsonrpc": "2.0",
                    "method": "eth_call",
                    "params": [
                        {
                            "to": token_address,
                            "data": data
                        },
                        "latest"
                    ],
                    "id": 1
                }
                
                response = requests.post(POLYGON_RPC_URL, json=payload, timeout=10)
                result = response.json()
                
                if "result" in result:
                    # Convert hex to decimal, USDC has 6 decimals
                    balance_raw = int(result["result"], 16)
                    balance = balance_raw / 1_000_000
                    
                    if balance > 0:
                        print(f"[DEBUG] {token_name} balance: ${balance:.2f}")
                        total_balance += balance
            
            wallet_type = "proxy" if (self.funder and self.signature_type > 0) else "Direct EOA"
            print(f"[DEBUG] Total {wallet_type} wallet balance: {check_address[:10]}... = ${total_balance:.2f}")
            
            return {
                "usdc": total_balance,
                "address": check_address
            }
                
        except Exception as e:
            return {"error": f"Balance fetch failed: {str(e)}"}

    def _get_best_ask(self, orderbook) -> Optional[float]:
        """Extract best ask price from orderbook.

        Args:
            orderbook: OrderBookSummary object or dict from API

        Returns:
            Best ask price or None if no asks available
        """
        # Handle OrderBookSummary object (py_clob_client response)
        if hasattr(orderbook, 'asks'):
            asks = orderbook.asks
        elif isinstance(orderbook, dict):
            asks = orderbook.get("asks", [])
        else:
            print(f"[DEBUG] Unexpected orderbook type: {type(orderbook)}")
            return None

        if not asks:
            print(f"[DEBUG] No asks found in orderbook")
            return None

        # Asks are typically sorted lowest to highest
        # Each ask is either an OrderSummary object or [price, size] tuple
        try:
            first_ask = asks[0]
            # Handle OrderSummary object
            if hasattr(first_ask, 'price'):
                best_ask = float(first_ask.price)
            # Handle tuple/list format
            else:
                best_ask = float(first_ask[0])
            
            print(f"[DEBUG] Best ask found: {best_ask}")
            return best_ask
        except (IndexError, ValueError, TypeError, AttributeError) as e:
            print(f"[DEBUG] Error parsing asks: {e}, asks={asks}")
            return None

    def _get_best_bid(self, orderbook) -> Optional[float]:
        """Extract best bid price from orderbook.

        Args:
            orderbook: OrderBookSummary object or dict from API

        Returns:
            Best bid price or None if no bids available
        """
        # Handle OrderBookSummary object (py_clob_client response)
        if hasattr(orderbook, 'bids'):
            bids = orderbook.bids
        elif isinstance(orderbook, dict):
            bids = orderbook.get("bids", [])
        else:
            print(f"[DEBUG] Unexpected orderbook type: {type(orderbook)}")
            return None

        if not bids:
            print(f"[DEBUG] No bids found in orderbook")
            return None

        # Bids are typically sorted highest to lowest
        # Each bid is either an OrderSummary object or [price, size] tuple
        try:
            first_bid = bids[0]
            # Handle OrderSummary object
            if hasattr(first_bid, 'price'):
                best_bid = float(first_bid.price)
            # Handle tuple/list format
            else:
                best_bid = float(first_bid[0])
            
            print(f"[DEBUG] Best bid found: {best_bid}")
            return best_bid
        except (IndexError, ValueError, TypeError, AttributeError) as e:
            print(f"[DEBUG] Error parsing bids: {e}, bids={bids}")
            return None


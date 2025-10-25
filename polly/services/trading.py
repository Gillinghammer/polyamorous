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
# CTF (Conditional Token Framework) contract
CTF_CONTRACT_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
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

# ERC1155 ABI for setApprovalForAll (CTF tokens)
ERC1155_APPROVAL_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "operator", "type": "address"},
            {"name": "approved", "type": "bool"}
        ],
        "name": "setApprovalForAll",
        "outputs": [],
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
            print("[DEBUG] Checking if allowances are already set...")
            
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
            
            # Check if allowances are already sufficient
            print(f"[DEBUG] Checking existing allowances for {account.address[:10]}...")
            
            # ABI for checking allowance
            check_allowance_abi = [
                {
                    "constant": True,
                    "inputs": [
                        {"name": "owner", "type": "address"},
                        {"name": "spender", "type": "address"}
                    ],
                    "name": "allowance",
                    "outputs": [{"name": "", "type": "uint256"}],
                    "type": "function"
                }
            ]
            
            # Check USDC.e allowance (since that's what you have)
            usdc_e_contract = w3.eth.contract(
                address=Web3.to_checksum_address(USDC_E_CONTRACT_ADDRESS),
                abi=check_allowance_abi
            )
            
            current_allowance = usdc_e_contract.functions.allowance(
                account.address,
                Web3.to_checksum_address(CTF_EXCHANGE_ADDRESS)
            ).call()
            
            print(f"[DEBUG] Current USDC.e allowance: {current_allowance}")
            
            # If allowance is already max, we're good
            if current_allowance > 10**12:  # More than 1M USDC worth
                print(f"[DEBUG] Allowances already set! Skipping approval.")
                return (True, "Allowances already configured (no new transaction needed)")
            
            # Max uint256 for unlimited approval
            max_approval = 2**256 - 1
            
            # Approve both USDC (for buying) and CTF tokens (for selling)
            print(f"[DEBUG] Approving from EOA wallet: {account.address[:10]}...")
            
            # 1. Approve USDC/USDC.e for buying (ERC20)
            usdc_contracts = [
                ("USDC.e (bridged)", USDC_E_CONTRACT_ADDRESS),
                ("USDC (native)", USDC_CONTRACT_ADDRESS)
            ]
            
            last_tx_hash = None
            for token_name, token_address in usdc_contracts:
                print(f"[DEBUG] Approving {token_name} for buying...")
                
                usdc_contract = w3.eth.contract(
                    address=Web3.to_checksum_address(token_address),
                    abi=ERC20_APPROVE_ABI
                )
                
                # Build approve transaction
                approve_txn = usdc_contract.functions.approve(
                    Web3.to_checksum_address(CTF_EXCHANGE_ADDRESS),
                    max_approval
                ).build_transaction({
                    'from': account.address,
                    'nonce': w3.eth.get_transaction_count(account.address),
                    'gas': 100000,
                    'gasPrice': w3.eth.gas_price,
                    'chainId': self.chain_id
                })
                
                signed_txn = account.sign_transaction(approve_txn)
                tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
                last_tx_hash = tx_hash
                
                print(f"[DEBUG] {token_name} approval tx: {tx_hash.hex()[:16]}...")
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
                
                if receipt['status'] == 1:
                    print(f"[DEBUG] ✓ {token_name} approved! Block: {receipt['blockNumber']}")
                else:
                    return (False, f"{token_name} approval failed. Tx: {tx_hash.hex()}")
            
            # 2. Approve CTF tokens for selling (ERC1155 - setApprovalForAll)
            print(f"[DEBUG] Approving CTF tokens for selling...")
            
            ctf_contract = w3.eth.contract(
                address=Web3.to_checksum_address(CTF_CONTRACT_ADDRESS),
                abi=ERC1155_APPROVAL_ABI
            )
            
            # Build setApprovalForAll transaction
            ctf_approval_txn = ctf_contract.functions.setApprovalForAll(
                Web3.to_checksum_address(CTF_EXCHANGE_ADDRESS),
                True  # Approve all CTF tokens
            ).build_transaction({
                'from': account.address,
                'nonce': w3.eth.get_transaction_count(account.address),
                'gas': 100000,
                'gasPrice': w3.eth.gas_price,
                'chainId': self.chain_id
            })
            
            signed_ctf_txn = account.sign_transaction(ctf_approval_txn)
            ctf_tx_hash = w3.eth.send_raw_transaction(signed_ctf_txn.raw_transaction)
            
            print(f"[DEBUG] CTF approval tx: {ctf_tx_hash.hex()[:16]}...")
            ctf_receipt = w3.eth.wait_for_transaction_receipt(ctf_tx_hash, timeout=120)
            
            if ctf_receipt['status'] == 1:
                print(f"[DEBUG] ✓ CTF tokens approved! Block: {ctf_receipt['blockNumber']}")
                return (True, f"All allowances approved! USDC for buying, CTF for selling.")
            else:
                return (False, f"CTF approval failed. Tx: {ctf_tx_hash.hex()}")
                
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
        
        Calculates shares from stake amount and executes via limit order at best ask price.

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
            FOK = getattr(OrderType, "FOK")

            # Get market price using price API (no orderbooks needed!)
            try:
                # Get buy price - this is what you'll pay
                buy_price_data = self._client.get_price(token_id, side="BUY")
                buy_price = float(buy_price_data.get("price", 0)) if isinstance(buy_price_data, dict) else 0
                
                if buy_price == 0:
                    return TradeExecutionResult(
                        success=False,
                        order_id=None,
                        error=f"No market price available for this token",
                        executed_price=0.0,
                        executed_size=0.0,
                    )
                
            except Exception as price_error:
                return TradeExecutionResult(
                    success=False,
                    order_id=None,
                    error=f"Could not fetch market price: {price_error}",
                    executed_price=0.0,
                    executed_size=0.0,
                )

            # Ensure stake meets Polymarket's $1 minimum
            if stake_amount < 1.0:
                stake_amount = 1.01
            
            # DON'T calculate shares - just pass dollar amount
            # According to docs: For BUY side, amount should be dollar amount to spend
            
            # Use MarketOrderArgs - pass DOLLAR amount for BUY
            MarketOrderArgs = getattr(clob_types, "MarketOrderArgs")
            
            market_order = MarketOrderArgs(
                token_id=token_id,
                amount=stake_amount,  # DOLLAR amount to spend (for BUY side per docs)
                side=BUY,
                order_type=FOK
            )
            
            # Refresh API credentials
            try:
                creds = self._client.create_or_derive_api_creds()
                self._client.set_api_creds(creds)
            except Exception as cred_error:
                pass
            
            # Sign and post market order
            signed_order = self._client.create_market_order(market_order)
            
            try:
                resp = self._client.post_order(signed_order, FOK)
            except Exception as post_error:
                # Handle allowance errors with retry (same as limit orders)
                error_detail = str(post_error)
                if hasattr(post_error, 'error_message') and isinstance(post_error.error_message, dict):
                    error_detail = post_error.error_message.get('error', error_detail)
                
                if "balance / allowance" in error_detail or "allowance" in error_detail.lower():
                    print(f"\n[yellow]USDC allowance required. Attempting to approve...[/yellow]")
                    print(f"[dim]This is a one-time on-chain transaction (costs ~$0.01 in gas)[/dim]\n")
                    
                    allowance_ok, allowance_msg = self.approve_allowance()
                    
                    if allowance_ok:
                        print(f"\n[green]✓ Allowance approved![/green]")
                        print(f"[dim]Retrying trade...[/dim]\n")
                        import time
                        time.sleep(5)
                        
                        # Retry
                        resp = self._client.post_order(signed_order, FOK)
                    else:
                        return TradeExecutionResult(
                            success=False,
                            order_id=None,
                            error=f"Failed to approve allowance: {allowance_msg}",
                            executed_price=0.0,
                            executed_size=0.0,
                        )
                else:
                    return TradeExecutionResult(
                        success=False,
                        order_id=None,
                        error=f"{error_detail}",
                        executed_price=0.0,
                        executed_size=0.0,
                    )
            
            # Extract execution details from response
            if isinstance(resp, dict):
                success = resp.get("success", False)
                order_id = resp.get("orderID")
                error = resp.get("error")
                
                # Get actual execution amounts
                # For BUY market orders (confirmed via API testing):
                # - makingAmount = USDC you're spending
                # - takingAmount = Shares you're receiving
                making_amount = resp.get("makingAmount")
                taking_amount = resp.get("takingAmount")
                
                actual_price = 0.0
                actual_size = 0.0
                
                if taking_amount and making_amount:
                    try:
                        actual_spent = float(making_amount)  # USDC spent
                        actual_shares = float(taking_amount)  # Shares received
                        if actual_shares > 0:
                            actual_price = actual_spent / actual_shares
                            actual_size = actual_shares
                    except (ValueError, ZeroDivisionError):
                        pass
                
                if error and not success:
                    error = f"{error} | Response: {resp}"
                    
                return TradeExecutionResult(
                    success=success,
                    order_id=order_id,
                    error=error,
                    executed_price=actual_price,
                    executed_size=actual_size,
                )
            else:
                return TradeExecutionResult(
                    success=False,
                    order_id=None,
                    error=f"Unexpected response type: {type(resp)}",
                    executed_price=0.0,
                    executed_size=0.0,
                )
            
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'message'):
                error_msg = e.message
            elif hasattr(e, 'args') and e.args:
                error_msg = str(e.args[0])
            
            return TradeExecutionResult(
                success=False,
                order_id=None,
                error=f"Exception during market order: {type(e).__name__}: {error_msg}",
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
            orderbook = self._client.get_order_book(token_id)
            
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
                creds = self._client.create_or_derive_api_creds()
                self._client.set_api_creds(creds)
            except Exception as cred_error:
                pass
            
            # Note: We'll handle allowances if we get an error during order posting
            
            # Sign the order
            signed_order = self._client.create_order(order_args)

            # Post as Good-Till-Cancelled order
            try:
                resp = self._client.post_order(signed_order, OrderType.GTC)
            except Exception as post_error:
                # Extract more details from the error
                error_detail = str(post_error)
                
                # Try to extract error details from PolyApiException
                if hasattr(post_error, 'error_message'):
                    # Extract actual error from dict if available
                    if isinstance(post_error.error_message, dict):
                        actual_error = post_error.error_message.get('error', error_detail)
                        error_detail = actual_error
                
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
                            if hasattr(retry_error, 'error_message'):
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

            # Check response and extract ACTUAL execution details
            if isinstance(resp, dict):
                success = resp.get("success", False)
                order_id = resp.get("orderID")
                error = resp.get("error")
                
                # Extract actual execution from Polymarket response
                # For BUY limit orders (same as market orders):
                # - makingAmount = USDC you're spending  
                # - takingAmount = Shares you're receiving
                making_amount = resp.get("makingAmount")  # USDC spent
                taking_amount = resp.get("takingAmount")  # Shares received
                
                if taking_amount and making_amount:
                    try:
                        actual_spent = float(making_amount)
                        actual_shares = float(taking_amount)
                        if actual_shares > 0:
                            actual_price = actual_spent / actual_shares
                            # Update with actual execution values
                            price = actual_price
                            size = actual_shares
                    except (ValueError, ZeroDivisionError):
                        pass
                
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
        
        Uses limit order at best bid price with FOK (Fill-Or-Kill) for immediate execution.

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
            FOK = getattr(OrderType, "FOK")

            # Fetch orderbook to check spread and show info
            orderbook = self._client.get_order_book(token_id)
            
            best_bid = self._get_best_bid(orderbook)
            best_ask = self._get_best_ask(orderbook)

            if best_bid is None:
                return TradeExecutionResult(
                    success=False,
                    order_id=None,
                    error=f"No liquidity available (no bids in orderbook)",
                    executed_price=0.0,
                    executed_size=0.0,
                )
            
            # Create limit sell order at best bid price (market taker)
            order_args = OrderArgs(
                token_id=token_id,
                price=best_bid,  # Match best bid price exactly
                size=size,
                side=SELL
            )

            # Sign and post the order
            signed_order = self._client.create_order(order_args)

            # Post as Fill-Or-Kill (immediate execution or cancel)
            try:
                resp = self._client.post_order(signed_order, FOK)
            except Exception as post_error:
                # Extract detailed error
                error_detail = str(post_error)
                if hasattr(post_error, 'error_message'):
                    if isinstance(post_error.error_message, dict):
                        error_detail = post_error.error_message.get('error', error_detail)
                
                # Handle allowance error with automatic approval for SELL orders
                if "balance / allowance" in error_detail or "allowance" in error_detail.lower():
                    print(f"\n[yellow]CTF token allowance required for selling. Attempting to approve...[/yellow]")
                    print(f"[dim]This is a one-time on-chain transaction (costs ~$0.01 in gas)[/dim]\n")
                    
                    allowance_ok, allowance_msg = self.approve_allowance()
                    
                    if allowance_ok:
                        print(f"\n[green]✓ Allowance approved successfully![/green]")
                        print(f"[dim]Waiting for blockchain state to propagate...[/dim]")
                        
                        # Give the blockchain a moment to propagate the allowance
                        import time
                        time.sleep(5)
                        
                        print(f"[dim]Retrying sell order...[/dim]\n")
                        
                        # Retry the sell order
                        try:
                            resp = self._client.post_order(signed_order, FOK)
                            
                            # Extract execution from retry
                            retry_price = 0.0
                            retry_size = 0.0
                            
                            if isinstance(resp, dict):
                                success = resp.get("success", False)
                                order_id = resp.get("orderID")
                                error = resp.get("error")
                                
                                taking = resp.get("takingAmount")
                                making = resp.get("makingAmount")
                                if taking and making:
                                    try:
                                        shares_sold = float(taking)
                                        usdc_received = float(making)
                                        if shares_sold > 0:
                                            retry_price = usdc_received / shares_sold
                                            retry_size = shares_sold
                                    except (ValueError, ZeroDivisionError):
                                        pass
                                
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
                                executed_price=retry_price,
                                executed_size=retry_size,
                            )
                        except Exception as retry_error:
                            retry_detail = str(retry_error)
                            if hasattr(retry_error, 'error_message') and isinstance(retry_error.error_message, dict):
                                retry_detail = retry_error.error_message.get('error', retry_detail)
                            
                            return TradeExecutionResult(
                                success=False,
                                order_id=None,
                                error=f"Sell retry failed: {retry_detail}",
                                executed_price=0.0,
                                executed_size=0.0,
                            )
                    else:
                        error_detail = f"Failed to approve allowance: {allowance_msg}"
                
                # Provide helpful error message for other errors
                elif "invalid amount" in error_detail or "min size" in error_detail:
                    pass  # Already clear
                
                return TradeExecutionResult(
                    success=False,
                    order_id=None,
                    error=f"{error_detail}",
                    executed_price=0.0,
                    executed_size=0.0,
                )

            # Extract execution details from response
            if isinstance(resp, dict):
                success = resp.get("success", False)
                order_id = resp.get("orderID")
                error = resp.get("error")
                
                # Get actual execution amounts
                # For SELL orders:
                # - makingAmount = Shares you're selling (what you make/offer)
                # - takingAmount = USDC you're receiving (what you take/get)
                making_amount = resp.get("makingAmount")  # Shares sold
                taking_amount = resp.get("takingAmount")  # USDC received
                
                actual_price = 0.0
                actual_size = 0.0
                
                if taking_amount and making_amount:
                    try:
                        actual_shares = float(making_amount)  # Shares sold
                        actual_received = float(taking_amount)  # USDC received
                        if actual_shares > 0:
                            actual_price = actual_received / actual_shares
                            actual_size = actual_shares
                    except (ValueError, ZeroDivisionError):
                        pass
                
                if error and not success:
                    error = f"{error} | Response: {resp}"
                    
                return TradeExecutionResult(
                    success=success,
                    order_id=order_id,
                    error=error,
                    executed_price=actual_price,
                    executed_size=actual_size,
                )
            else:
                return TradeExecutionResult(
                    success=False,
                    order_id=None,
                    error=f"Unexpected response type: {type(resp)}",
                    executed_price=0.0,
                    executed_size=0.0,
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
                error=f"Exception during market sell: {type(e).__name__}: {error_msg}",
                executed_price=0.0,
                executed_size=0.0,
            )

    def get_live_positions(self) -> list[dict]:
        """Fetch live positions from Polymarket Data API.
        
        Returns:
            List of position dictionaries with current values and P&L
        """
        try:
            import requests
            
            # Use the EOA address for Direct EOA mode, or funder for proxy mode
            user_address = self.funder if (self.funder and self.signature_type > 0) else self._address
            
            url = f"https://data-api.polymarket.com/positions?user={user_address}"
            
            print(f"[DEBUG] Fetching positions from Polymarket Data API for {user_address[:10]}...")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                positions = response.json()
                print(f"[DEBUG] Found {len(positions)} positions")
                return positions
            else:
                print(f"[DEBUG] Positions API error: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"[DEBUG] Failed to fetch positions: {e}")
            return []
    
    def get_balances(self) -> dict:
        """Get wallet balances (USDC and positions).

        Returns:
            Dictionary with balance information (usdc, address)
        """
        try:
            # Try using Polymarket API to get balance first
            if hasattr(self._client, 'get_balance_allowance'):
                try:
                    balance_data = self._client.get_balance_allowance()
                    # Extract USDC balance from response
                    if isinstance(balance_data, dict):
                        usdc_balance = float(balance_data.get('balance', 0)) / 1_000_000  # Convert from wei
                        return {
                            "usdc": usdc_balance,
                            "address": self.funder if self.funder else self._address
                        }
                except Exception as api_error:
                    pass
            
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
                        total_balance += balance
            
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
            return None

        if not asks:
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
            
            return best_ask
        except (IndexError, ValueError, TypeError, AttributeError) as e:
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
            return None

        if not bids:
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
            
            return best_bid
        except (IndexError, ValueError, TypeError, AttributeError) as e:
            return None

